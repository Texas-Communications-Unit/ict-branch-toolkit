import type {
  OfflineMutation,
  OfflinePackage,
  OfflineSynchronizationResult,
} from "./types";

const DATABASE_NAME = "ict-toolkit-offline-v1";
const DATABASE_VERSION = 1;
const PACKAGE_STORE = "encrypted-packages";
const KEY_ITERATIONS = 310_000;
const MINIMUM_PASSPHRASE_LENGTH = 12;
const textEncoder = new TextEncoder();
const textDecoder = new TextDecoder();

export interface OfflineVault {
  schema_version: "offline-vault-v1";
  package: OfflinePackage;
  mutations: OfflineMutation[];
  cancelled_mutation_ids: string[];
  updated_at: string;
}

export interface EncryptedOfflineEnvelope {
  id: string;
  incident: string;
  status: OfflinePackage["status"];
  expires_at: string;
  manifest_sha256: string;
  salt_base64: string;
  iv_base64: string;
  ciphertext_base64: string;
  updated_at: string;
}

export interface QueueMutationInput {
  operation: OfflineMutation["operation"];
  revision_id: string;
  object_id: string | null;
  payload: Record<string, unknown>;
  base_updated_at: string | null;
}

function sortForCanonicalJson(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sortForCanonicalJson);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, item]) => [key, sortForCanonicalJson(item)]),
    );
  }
  return value;
}

export function canonicalJson(value: unknown): string {
  return JSON.stringify(sortForCanonicalJson(value));
}

async function sha256(value: unknown): Promise<string> {
  const bytes = await crypto.subtle.digest(
    "SHA-256",
    textEncoder.encode(canonicalJson(value)),
  );
  return [...new Uint8Array(bytes)]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

function toBase64(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}

function fromBase64(value: string): Uint8Array<ArrayBuffer> {
  const binary = atob(value);
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

async function deriveKey(
  passphrase: string,
  salt: Uint8Array<ArrayBuffer>,
): Promise<CryptoKey> {
  if (passphrase.length < MINIMUM_PASSPHRASE_LENGTH) {
    throw new Error(
      `Use an offline passphrase of at least ${MINIMUM_PASSPHRASE_LENGTH} characters.`,
    );
  }
  const material = await crypto.subtle.importKey(
    "raw",
    textEncoder.encode(passphrase),
    "PBKDF2",
    false,
    ["deriveKey"],
  );
  return crypto.subtle.deriveKey(
    {
      name: "PBKDF2",
      hash: "SHA-256",
      salt,
      iterations: KEY_ITERATIONS,
    },
    material,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"],
  );
}

function associatedData(
  packageId: string,
  manifestSha256: string,
): Uint8Array<ArrayBuffer> {
  return textEncoder.encode(
    canonicalJson({
      schema_version: "offline-envelope-v1",
      package_id: packageId,
      manifest_sha256: manifestSha256,
    }),
  );
}

export async function encryptOfflineVault(
  vault: OfflineVault,
  passphrase: string,
  existingSaltBase64?: string,
): Promise<EncryptedOfflineEnvelope> {
  const salt = existingSaltBase64
    ? fromBase64(existingSaltBase64)
    : crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const key = await deriveKey(passphrase, salt);
  const ciphertext = await crypto.subtle.encrypt(
    {
      name: "AES-GCM",
      iv,
      additionalData: associatedData(
        vault.package.id,
        vault.package.manifest_sha256,
      ),
    },
    key,
    textEncoder.encode(canonicalJson(vault)),
  );
  return {
    id: vault.package.id,
    incident: vault.package.incident,
    status: vault.package.status,
    expires_at: vault.package.expires_at,
    manifest_sha256: vault.package.manifest_sha256,
    salt_base64: toBase64(salt),
    iv_base64: toBase64(iv),
    ciphertext_base64: toBase64(new Uint8Array(ciphertext)),
    updated_at: new Date().toISOString(),
  };
}

export async function decryptOfflineVault(
  envelope: EncryptedOfflineEnvelope,
  passphrase: string,
): Promise<OfflineVault> {
  try {
    const salt = fromBase64(envelope.salt_base64);
    const key = await deriveKey(passphrase, salt);
    const plaintext = await crypto.subtle.decrypt(
      {
        name: "AES-GCM",
        iv: fromBase64(envelope.iv_base64),
        additionalData: associatedData(envelope.id, envelope.manifest_sha256),
      },
      key,
      fromBase64(envelope.ciphertext_base64),
    );
    const vault = JSON.parse(textDecoder.decode(plaintext)) as OfflineVault;
    if (
      vault.schema_version !== "offline-vault-v1" ||
      vault.package.id !== envelope.id ||
      vault.package.manifest_sha256 !== envelope.manifest_sha256
    ) {
      throw new Error(
        "The encrypted package identity does not match its envelope.",
      );
    }
    return vault;
  } catch (error) {
    if (
      error instanceof Error &&
      error.message.startsWith("Use an offline passphrase")
    ) {
      throw error;
    }
    throw new Error(
      "Unable to unlock the package. Verify the passphrase and package integrity.",
      { cause: error },
    );
  }
}

function openDatabase(): Promise<IDBDatabase> {
  if (!("indexedDB" in globalThis)) {
    return Promise.reject(
      new Error("Encrypted offline storage is not available in this browser."),
    );
  }
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE_NAME, DATABASE_VERSION);
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains(PACKAGE_STORE)) {
        request.result.createObjectStore(PACKAGE_STORE, { keyPath: "id" });
      }
    };
    request.onerror = () =>
      reject(
        new Error(
          request.error?.message ?? "Unable to open encrypted offline storage.",
        ),
      );
    request.onsuccess = () => resolve(request.result);
  });
}

async function transact<T>(
  mode: IDBTransactionMode,
  operation: (store: IDBObjectStore) => IDBRequest<T>,
): Promise<T> {
  const database = await openDatabase();
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(PACKAGE_STORE, mode);
    const request = operation(transaction.objectStore(PACKAGE_STORE));
    let result: T;
    let settled = false;
    const fail = (error: DOMException | null) => {
      if (settled) return;
      settled = true;
      database.close();
      reject(
        new Error(
          error?.name === "QuotaExceededError"
            ? "The device storage limit was reached. Purge an old package or reduce the selection."
            : (error?.message ?? "Offline storage operation failed."),
          { cause: error ?? undefined },
        ),
      );
    };
    request.onsuccess = () => {
      result = request.result;
    };
    request.onerror = () => fail(request.error);
    transaction.oncomplete = () => {
      if (settled) return;
      settled = true;
      database.close();
      resolve(result);
    };
    transaction.onerror = () => fail(transaction.error);
    transaction.onabort = () => fail(transaction.error);
  });
}

export async function listLocalPackageMetadata(): Promise<
  EncryptedOfflineEnvelope[]
> {
  return transact("readonly", (store) => store.getAll());
}

export async function getLocalPackageEnvelope(
  packageId: string,
): Promise<EncryptedOfflineEnvelope | undefined> {
  return transact("readonly", (store) => store.get(packageId));
}

async function putEnvelope(
  envelope: EncryptedOfflineEnvelope,
): Promise<EncryptedOfflineEnvelope> {
  await assertStorageCapacity(
    fromBase64(envelope.ciphertext_base64).byteLength,
  );
  await transact("readwrite", (store) => store.put(envelope));
  return envelope;
}

export async function savePackageToDevice(
  offlinePackage: OfflinePackage,
  passphrase: string,
): Promise<OfflineVault> {
  const vault: OfflineVault = {
    schema_version: "offline-vault-v1",
    package: offlinePackage,
    mutations: [],
    cancelled_mutation_ids: [],
    updated_at: new Date().toISOString(),
  };
  await putEnvelope(await encryptOfflineVault(vault, passphrase));
  return vault;
}

export async function unlockLocalPackage(
  packageId: string,
  passphrase: string,
): Promise<OfflineVault> {
  const envelope = await getLocalPackageEnvelope(packageId);
  if (!envelope) throw new Error("This package is not stored on this device.");
  if (Date.parse(envelope.expires_at) <= Date.now()) {
    throw new Error(
      "This local package expired and cannot be unlocked. Purge it from the device.",
    );
  }
  return decryptOfflineVault(envelope, passphrase);
}

async function persistVault(
  vault: OfflineVault,
  passphrase: string,
): Promise<void> {
  vault.updated_at = new Date().toISOString();
  const existing = await getLocalPackageEnvelope(vault.package.id);
  await putEnvelope(
    await encryptOfflineVault(vault, passphrase, existing?.salt_base64),
  );
}

export async function queueOfflineMutation(
  vault: OfflineVault,
  passphrase: string,
  input: QueueMutationInput,
): Promise<OfflineVault> {
  const mutation = await buildOfflineMutation(vault, input);
  const updated = {
    ...vault,
    mutations: [...vault.mutations, mutation],
  };
  await persistVault(updated, passphrase);
  return updated;
}

export async function buildOfflineMutation(
  vault: OfflineVault,
  input: QueueMutationInput,
): Promise<OfflineMutation> {
  const pendingTail = vault.mutations.at(-1);
  const previousHash =
    pendingTail?.mutation_sha256 ?? vault.package.last_chain_sha256;
  const sequence =
    pendingTail?.sequence !== undefined
      ? pendingTail.sequence + 1
      : vault.package.last_sequence + 1;
  const mutationId = crypto.randomUUID();
  const occurredAtClient = new Date().toISOString();
  const payloadSha256 = await sha256(input.payload);
  const document = {
    schema_version: "offline-mutation-v1",
    package_id: vault.package.id,
    mutation_id: mutationId,
    sequence,
    actor_id: vault.package.requested_by,
    device_id: vault.package.device_id,
    operation: input.operation,
    object_id: input.object_id,
    revision_id: input.revision_id,
    previous_hash: previousHash,
    payload_sha256: payloadSha256,
    base_updated_at: input.base_updated_at,
    occurred_at_client: occurredAtClient,
  };
  return {
    id: mutationId,
    sequence,
    actor_id: vault.package.requested_by,
    device_id: vault.package.device_id,
    operation: input.operation,
    object_id: input.object_id,
    revision_id: input.revision_id,
    previous_hash: previousHash,
    payload_sha256: payloadSha256,
    mutation_sha256: await sha256(document),
    payload: input.payload,
    base_updated_at: input.base_updated_at,
    occurred_at_client: occurredAtClient,
  };
}

export async function cancelPendingMutation(
  vault: OfflineVault,
  passphrase: string,
  mutationId: string,
): Promise<OfflineVault> {
  const index = vault.mutations.findIndex((item) => item.id === mutationId);
  if (index < 0) throw new Error("The pending change was not found.");
  if (vault.mutations[index].sync_status) {
    throw new Error(
      "A server-received change requires an explicit conflict decision.",
    );
  }
  if (index !== vault.mutations.length - 1) {
    throw new Error(
      "Cancel later queued changes first so the ordered hash chain remains intact.",
    );
  }
  const updated = {
    ...vault,
    mutations: vault.mutations.slice(0, -1),
    cancelled_mutation_ids: [...vault.cancelled_mutation_ids, mutationId],
  };
  await persistVault(updated, passphrase);
  return updated;
}

export async function applySynchronizationResult(
  vault: OfflineVault,
  passphrase: string,
  result: OfflineSynchronizationResult,
): Promise<OfflineVault> {
  const byId = new Map(result.results.map((item) => [item.id, item]));
  const mutations = vault.mutations.flatMap((mutation) => {
    const item = byId.get(mutation.id);
    if (!item) return [mutation];
    if (item.status === "applied" || item.status === "duplicate") return [];
    return [
      {
        ...mutation,
        sync_status: item.status,
        sync_result: item.result,
      } as OfflineMutation,
    ];
  });
  const updated: OfflineVault = {
    ...vault,
    package: {
      ...vault.package,
      status: result.status,
      current_status: result.status,
      last_sequence: result.last_sequence,
      last_chain_sha256: result.last_chain_sha256,
    },
    mutations,
  };
  await persistVault(updated, passphrase);
  return updated;
}

export async function removeResolvedMutation(
  vault: OfflineVault,
  passphrase: string,
  mutationId: string,
): Promise<OfflineVault> {
  const updated = {
    ...vault,
    mutations: vault.mutations.filter((item) => item.id !== mutationId),
  };
  await persistVault(updated, passphrase);
  return updated;
}

export async function purgeLocalPackage(packageId: string): Promise<void> {
  await transact("readwrite", (store) => store.delete(packageId));
}

export async function purgeExpiredLocalPackages(
  now = Date.now(),
): Promise<number> {
  const envelopes = await listLocalPackageMetadata();
  const expired = envelopes.filter(
    (envelope) => Date.parse(envelope.expires_at) <= now,
  );
  await Promise.all(expired.map((envelope) => purgeLocalPackage(envelope.id)));
  return expired.length;
}

export function createLocalSupportBundle(
  vault: OfflineVault,
): Record<string, unknown> {
  return {
    schema_version: "offline-local-support-v1",
    generated_at: new Date().toISOString(),
    package: {
      id: vault.package.id,
      status: vault.package.status,
      manifest_sha256: vault.package.manifest_sha256,
      device_id: vault.package.device_id,
      expires_at: vault.package.expires_at,
      last_sequence: vault.package.last_sequence,
      last_chain_sha256: vault.package.last_chain_sha256,
    },
    queue: vault.mutations.map((mutation) => ({
      id: mutation.id,
      sequence: mutation.sequence,
      operation: mutation.operation,
      mutation_sha256: mutation.mutation_sha256,
      sync_status: mutation.sync_status ?? "pending",
      result_code: mutation.sync_result?.code ?? null,
    })),
    cancelled_mutation_ids: vault.cancelled_mutation_ids,
    excluded: [
      "passphrase",
      "encryption key",
      "authentication token",
      "ciphertext",
      "package payload",
      "mutation payload",
    ],
  };
}

export async function assertStorageCapacity(
  requiredBytes: number,
): Promise<void> {
  if (!navigator.storage?.estimate) return;
  const estimate = await navigator.storage.estimate();
  if (
    estimate.quota !== undefined &&
    estimate.usage !== undefined &&
    requiredBytes > estimate.quota - estimate.usage
  ) {
    throw new Error(
      "The device storage limit was reached. Purge an old package or reduce the selection.",
    );
  }
}
