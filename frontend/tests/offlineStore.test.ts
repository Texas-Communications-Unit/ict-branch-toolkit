import {
  buildOfflineMutation,
  canonicalJson,
  createLocalSupportBundle,
  decryptOfflineVault,
  encryptOfflineVault,
  type OfflineVault,
} from "../src/offlineStore";
import type { OfflinePackage } from "../src/types";

function packageFixture(): OfflinePackage {
  return {
    id: "11111111-1111-4111-8111-111111111111",
    incident: "22222222-2222-4222-8222-222222222222",
    requested_by: 7,
    device_id: "33333333-3333-4333-8333-333333333333",
    status: "active",
    current_status: "active",
    scope: {
      revision_ids: ["44444444-4444-4444-8444-444444444444"],
      resource_release_ids: [],
      site_ids: [],
      terrain_analysis_ids: [],
      attachment_ids: [],
      include_map: false,
    },
    payload_snapshot: {
      schema_version: "offline-package-v1",
      incident: {
        name: "Sensitive synthetic exercise",
      },
      revisions: [],
    },
    manifest: {
      schema_version: "offline-package-v1",
      payload_sha256: "a".repeat(64),
      payload_bytes: 1024,
      classification: "Synthetic only",
    },
    manifest_sha256: "b".repeat(64),
    last_sequence: 0,
    last_chain_sha256: "b".repeat(64),
    expires_at: "2099-07-28T20:00:00Z",
    created_at: "2026-07-28T20:00:00Z",
    updated_at: "2026-07-28T20:00:00Z",
    locked_at: null,
    revoked_at: null,
    purged_at: null,
    receipts: [],
  };
}

function vaultFixture(): OfflineVault {
  return {
    schema_version: "offline-vault-v1",
    package: packageFixture(),
    mutations: [],
    cancelled_mutation_ids: [],
    updated_at: "2026-07-28T20:00:00Z",
  };
}

test("canonical JSON is stable across property insertion order", () => {
  expect(canonicalJson({ z: 1, a: { y: 2, b: 3 } })).toBe(
    canonicalJson({ a: { b: 3, y: 2 }, z: 1 }),
  );
});

test("encrypts package content and rejects an incorrect passphrase", async () => {
  const vault = vaultFixture();
  const envelope = await encryptOfflineVault(
    vault,
    "correct horse battery staple",
  );

  expect(envelope.ciphertext_base64).not.toContain(
    "Sensitive synthetic exercise",
  );
  await expect(
    decryptOfflineVault(envelope, "correct horse battery staple"),
  ).resolves.toEqual(vault);
  await expect(
    decryptOfflineVault(envelope, "incorrect passphrase"),
  ).rejects.toThrow("Unable to unlock");
});

test("builds an ordered mutation chain with stable actor and device context", async () => {
  const vault = vaultFixture();
  const first = await buildOfflineMutation(vault, {
    operation: "revision.update",
    revision_id: vault.package.scope.revision_ids[0],
    object_id: vault.package.scope.revision_ids[0],
    payload: { prepared_by_position: "COML" },
    base_updated_at: "2026-07-28T20:00:00Z",
  });
  const second = await buildOfflineMutation(
    { ...vault, mutations: [first] },
    {
      operation: "revision.update",
      revision_id: vault.package.scope.revision_ids[0],
      object_id: vault.package.scope.revision_ids[0],
      payload: { prepared_by_position: "COMC" },
      base_updated_at: "2026-07-28T20:00:00Z",
    },
  );

  expect(first.sequence).toBe(1);
  expect(first.previous_hash).toBe(vault.package.last_chain_sha256);
  expect(first.actor_id).toBe(7);
  expect(first.device_id).toBe(vault.package.device_id);
  expect(first.payload_sha256).toMatch(/^[0-9a-f]{64}$/);
  expect(first.mutation_sha256).toMatch(/^[0-9a-f]{64}$/);
  expect(second.sequence).toBe(2);
  expect(second.previous_hash).toBe(first.mutation_sha256);
});

test("support output excludes package and mutation payload content", async () => {
  const vault = vaultFixture();
  const mutation = await buildOfflineMutation(vault, {
    operation: "revision.update",
    revision_id: vault.package.scope.revision_ids[0],
    object_id: vault.package.scope.revision_ids[0],
    payload: { prepared_by_position: "Sensitive synthetic value" },
    base_updated_at: null,
  });
  const support = createLocalSupportBundle({
    ...vault,
    mutations: [mutation],
  });
  const serialized = JSON.stringify(support);

  expect(serialized).not.toContain("Sensitive synthetic exercise");
  expect(serialized).not.toContain("Sensitive synthetic value");
  expect(serialized).toContain(mutation.mutation_sha256);
  expect(serialized).toContain("authentication token");
});
