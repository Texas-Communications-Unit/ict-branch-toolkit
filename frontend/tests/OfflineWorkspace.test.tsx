import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { OfflineWorkspace } from "../src/OfflineWorkspace";
import type {
  Incident,
  OfflinePackage,
  OfflineStatus,
  PlanRevision,
} from "../src/types";
import type { OfflineVault } from "../src/offlineStore";

const api = vi.hoisted(() => ({
  createOfflinePackage: vi.fn(),
  getOfflineStatus: vi.fn(),
  getOfflineSupportBundle: vi.fn(),
  listConventionalChannels: vi.fn(),
  listOfflinePackages: vi.fn(),
  listPlans: vi.fn(),
  listRadioSites: vi.fn(),
  listTerrainAnalyses: vi.fn(),
  listTrunkedTalkgroups: vi.fn(),
  lockOfflinePackage: vi.fn(),
  purgeOfflinePackage: vi.fn(),
  resolveOfflineConflict: vi.fn(),
  synchronizeOfflinePackage: vi.fn(),
  unlockOfflinePackage: vi.fn(),
}));

const store = vi.hoisted(() => ({
  applySynchronizationResult: vi.fn(),
  cancelPendingMutation: vi.fn(),
  createLocalSupportBundle: vi.fn(),
  listLocalPackageMetadata: vi.fn(),
  purgeExpiredLocalPackages: vi.fn(),
  purgeLocalPackage: vi.fn(),
  queueOfflineMutation: vi.fn(),
  removeResolvedMutation: vi.fn(),
  savePackageToDevice: vi.fn(),
  unlockLocalPackage: vi.fn(),
}));

const serviceWorker = vi.hoisted(() => ({
  activateOfflineUpdate: vi.fn(),
  checkForOfflineUpdate: vi.fn(),
  clearOfflineRuntimeCaches: vi.fn(),
  SERVICE_WORKER_UPDATE_EVENT: "ict-toolkit-service-worker-update",
}));

vi.mock("../src/api", () => api);
vi.mock("../src/offlineStore", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../src/offlineStore")>()),
  ...store,
}));
vi.mock("../src/serviceWorker", () => serviceWorker);

const incident: Incident = {
  id: "22222222-2222-4222-8222-222222222222",
  name: "Synthetic offline exercise",
  incident_number: "SYN-OFFLINE",
  status: "planning",
  operational_periods: [],
  archived_at: null,
  permissions: ["plan.view", "plan.edit"],
};

const revision: PlanRevision = {
  id: "44444444-4444-4444-8444-444444444444",
  plan: "55555555-5555-4555-8555-555555555555",
  number: 1,
  status: "draft",
  is_locked: false,
  prepared_by_name: "Synthetic Planner",
  prepared_by_position: "",
  approved_at: null,
  created_at: "2026-07-28T20:00:00Z",
  updated_at: "2026-07-28T20:00:00Z",
  assignments: [],
  relationships: [],
};

const capability: OfflineStatus = {
  schema_version: "offline-package-v1",
  enabled: false,
  approved_for_non_synthetic_use: false,
  protection: {
    browser_storage: "AES-256-GCM encrypted IndexedDB envelope",
    key_derivation: "PBKDF2-SHA-256",
    key_persistence: "The unlock key remains in memory only.",
    limitation: "An unlocked or compromised browser remains exposed.",
  },
  supported_operations: ["revision.update", "assignment.update"],
  unsupported_operations: ["approve or publish a plan revision"],
  limits: {
    maximum_package_bytes: 5_242_880,
    maximum_queue_items: 500,
    default_expiration_hours: 24,
    maximum_expiration_hours: 72,
    clock_skew_tolerance_seconds: 300,
  },
  conflict_policy: "No last-writer-wins behavior.",
  classification: "Synthetic only",
  warning: "Human approval is required.",
};

function packageFixture(
  status: OfflinePackage["status"] = "active",
): OfflinePackage {
  return {
    id: "11111111-1111-4111-8111-111111111111",
    incident: incident.id,
    requested_by: 7,
    device_id: "33333333-3333-4333-8333-333333333333",
    status,
    current_status: status,
    scope: {
      revision_ids: [revision.id],
      resource_release_ids: [],
      site_ids: [],
      terrain_analysis_ids: [],
      attachment_ids: [],
      include_map: false,
    },
    payload_snapshot: {
      revisions: [revision],
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
    revoked_at: status === "revoked" ? "2026-07-28T20:30:00Z" : null,
    purged_at: null,
    receipts: [],
  };
}

function vaultFixture(
  status: OfflinePackage["status"] = "active",
): OfflineVault {
  return {
    schema_version: "offline-vault-v1",
    package: packageFixture(status),
    mutations: [],
    cancelled_mutation_ids: [],
    updated_at: "2026-07-28T20:00:00Z",
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  api.getOfflineStatus.mockResolvedValue(capability);
  api.listPlans.mockResolvedValue([
    {
      id: revision.plan,
      incident: incident.id,
      operational_period: "period-1",
      title: "Synthetic ICS-205",
      revisions: [revision],
    },
  ]);
  api.listRadioSites.mockResolvedValue([]);
  api.listTerrainAnalyses.mockResolvedValue({
    count: 0,
    next: null,
    previous: null,
    results: [],
  });
  api.listConventionalChannels.mockResolvedValue([]);
  api.listTrunkedTalkgroups.mockResolvedValue([]);
  api.listOfflinePackages.mockResolvedValue([]);
  store.listLocalPackageMetadata.mockResolvedValue([]);
  store.purgeExpiredLocalPackages.mockResolvedValue(0);
  serviceWorker.clearOfflineRuntimeCaches.mockResolvedValue(undefined);
  serviceWorker.checkForOfflineUpdate.mockResolvedValue(undefined);
  Object.defineProperty(navigator, "onLine", {
    configurable: true,
    value: true,
  });
});

test("shows fail-closed scope, connectivity changes, and safe cache clearing", async () => {
  render(<OfflineWorkspace incident={incident} />);

  expect(
    await screen.findByRole("heading", {
      name: "Offline and intermittent operation",
    }),
  ).toBeInTheDocument();
  expect(screen.getByText("Packaging disabled")).toBeInTheDocument();
  expect(
    screen.queryByRole("heading", {
      name: "Create an explicitly scoped encrypted package",
    }),
  ).not.toBeInTheDocument();

  fireEvent(window, new Event("offline"));
  expect(await screen.findByText("Offline")).toBeInTheDocument();
  expect(
    screen.getByText(/Only encrypted, explicitly packaged work/),
  ).toBeInTheDocument();
  fireEvent(window, new Event("online"));
  expect(await screen.findByText("Connected")).toBeInTheDocument();
  expect(
    screen.getByText(/Connection restored. Review pending changes/),
  ).toBeInTheDocument();

  fireEvent(window, new Event("ict-toolkit-service-worker-update"));
  await userEvent.click(
    await screen.findByRole("button", {
      name: "Activate downloaded update",
    }),
  );
  expect(serviceWorker.activateOfflineUpdate).toHaveBeenCalledOnce();

  await userEvent.click(
    screen.getByRole("button", { name: "Clear runtime caches" }),
  );
  expect(serviceWorker.clearOfflineRuntimeCaches).toHaveBeenCalledOnce();
  expect(
    screen.getByText(/Encrypted incident packages were not touched/),
  ).toBeInTheDocument();
});

test("loads and unlocks an encrypted device package after an offline restart", async () => {
  const active = packageFixture();
  Object.defineProperty(navigator, "onLine", {
    configurable: true,
    value: false,
  });
  api.getOfflineStatus.mockRejectedValue(new Error("Network unavailable"));
  store.listLocalPackageMetadata.mockResolvedValue([
    {
      id: active.id,
      incident: active.incident,
      status: active.status,
      expires_at: active.expires_at,
      manifest_sha256: active.manifest_sha256,
      salt_base64: "salt",
      iv_base64: "iv",
      ciphertext_base64: "ciphertext",
      updated_at: active.updated_at,
    },
  ]);
  store.unlockLocalPackage.mockResolvedValue(vaultFixture());
  render(<OfflineWorkspace incident={incident} />);

  expect(await screen.findByText("Offline")).toBeInTheDocument();
  await userEvent.selectOptions(
    await screen.findByLabelText("Package"),
    active.id,
  );
  await userEvent.type(
    screen.getByLabelText("Passphrase"),
    "synthetic passphrase",
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Unlock for this session" }),
  );

  expect(
    await screen.findByRole("heading", { name: "Unlocked package review" }),
  ).toBeInTheDocument();
  expect(store.unlockLocalPackage).toHaveBeenCalledWith(
    active.id,
    "synthetic passphrase",
  );
});

test("reports storage failure without claiming a local package was saved", async () => {
  api.getOfflineStatus.mockResolvedValue({ ...capability, enabled: true });
  api.createOfflinePackage.mockResolvedValue(packageFixture());
  store.savePackageToDevice.mockRejectedValue(
    new Error(
      "The device storage limit was reached. Purge an old package or reduce the selection.",
    ),
  );
  render(<OfflineWorkspace incident={incident} />);

  const passphrase = await screen.findByLabelText(
    "Device-only encryption passphrase",
  );
  await userEvent.type(passphrase, "synthetic passphrase");
  await waitFor(() =>
    expect(
      screen.getByRole("button", {
        name: "Encrypt package on this device",
      }),
    ).toBeEnabled(),
  );
  await userEvent.click(
    screen.getByRole("button", {
      name: "Encrypt package on this device",
    }),
  );

  expect(
    await screen.findByText(/device storage limit was reached/),
  ).toBeInTheDocument();
  expect(api.lockOfflinePackage).toHaveBeenCalledWith(packageFixture().id);
  expect(
    screen.getByText(
      /server package was locked because the device copy was not saved/,
    ),
  ).toBeInTheDocument();
  expect(
    screen.queryByText(/Package encrypted on this device/),
  ).not.toBeInTheDocument();
});

test("detects revoked access after unlock and keeps synchronization unavailable", async () => {
  const revoked = packageFixture("revoked");
  api.listOfflinePackages.mockResolvedValue([revoked]);
  store.listLocalPackageMetadata.mockResolvedValue([
    {
      id: revoked.id,
      incident: revoked.incident,
      status: "active",
      expires_at: revoked.expires_at,
      manifest_sha256: revoked.manifest_sha256,
      salt_base64: "salt",
      iv_base64: "iv",
      ciphertext_base64: "ciphertext",
      updated_at: revoked.updated_at,
    },
  ]);
  store.unlockLocalPackage.mockResolvedValue(vaultFixture("revoked"));
  render(<OfflineWorkspace incident={incident} />);

  await userEvent.selectOptions(
    await screen.findByLabelText("Package"),
    revoked.id,
  );
  await userEvent.type(
    screen.getByLabelText("Passphrase"),
    "synthetic passphrase",
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Unlock for this session" }),
  );

  expect(
    await screen.findByText(/Incident access was revoked/),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("button", {
      name: "Review complete — synchronize",
    }),
  ).toBeDisabled();
  expect(api.unlockOfflinePackage).not.toHaveBeenCalled();
});

test("removes the local key even when the server lock request fails", async () => {
  const active = packageFixture();
  api.listOfflinePackages.mockResolvedValue([active]);
  store.listLocalPackageMetadata.mockResolvedValue([
    {
      id: active.id,
      incident: active.incident,
      status: active.status,
      expires_at: active.expires_at,
      manifest_sha256: active.manifest_sha256,
      salt_base64: "salt",
      iv_base64: "iv",
      ciphertext_base64: "ciphertext",
      updated_at: active.updated_at,
    },
  ]);
  store.unlockLocalPackage.mockResolvedValue(vaultFixture());
  api.lockOfflinePackage.mockRejectedValue(new Error("Synthetic outage"));
  render(<OfflineWorkspace incident={incident} />);

  await userEvent.selectOptions(
    await screen.findByLabelText("Package"),
    active.id,
  );
  const passphrase = screen.getByLabelText("Passphrase");
  await userEvent.type(passphrase, "synthetic passphrase");
  await userEvent.click(
    screen.getByRole("button", { name: "Unlock for this session" }),
  );
  await userEvent.click(
    await screen.findByRole("button", { name: "Lock package" }),
  );

  expect(
    screen.queryByRole("heading", { name: "Unlocked package review" }),
  ).not.toBeInTheDocument();
  expect(passphrase).toHaveValue("");
  expect(
    screen.getByText(/server package could not be locked/i),
  ).toBeInTheDocument();
});

test("exposes each bounded operation and queues an assignment create with a stable ID", async () => {
  const active = packageFixture();
  const editableRevision: PlanRevision = {
    ...revision,
    assignments: [
      {
        id: "88888888-8888-4888-8888-888888888888",
        revision: revision.id,
        position: 1,
        function: "Command",
        channel_name: "SYN CMD",
        assignment: "Synthetic command",
        rx_frequency_hz: null,
        rx_squelch: "",
        tx_frequency_hz: null,
        tx_squelch: "",
        mode: "",
        remarks: "",
        structured_note: "",
        contact_name: "",
        site_address: "",
        phone_numbers: "",
        contact_24_hour: "",
        resource_snapshot: {},
        updated_at: "2026-07-28T20:00:00Z",
      },
    ],
  };
  const editableVault: OfflineVault = {
    ...vaultFixture(),
    package: {
      ...active,
      payload_snapshot: { revisions: [editableRevision] },
    },
  };
  api.listOfflinePackages.mockResolvedValue([active]);
  store.listLocalPackageMetadata.mockResolvedValue([
    {
      id: active.id,
      incident: active.incident,
      status: active.status,
      expires_at: active.expires_at,
      manifest_sha256: active.manifest_sha256,
      salt_base64: "salt",
      iv_base64: "iv",
      ciphertext_base64: "ciphertext",
      updated_at: active.updated_at,
    },
  ]);
  store.unlockLocalPackage.mockResolvedValue(editableVault);
  store.queueOfflineMutation.mockResolvedValue(editableVault);
  render(<OfflineWorkspace incident={incident} />);

  await userEvent.selectOptions(
    await screen.findByLabelText("Package"),
    active.id,
  );
  await userEvent.type(
    screen.getByLabelText("Passphrase"),
    "synthetic passphrase",
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Unlock for this session" }),
  );

  const operation = await screen.findByLabelText("Offline operation");
  expect(operation).toHaveTextContent("Update revision prepared-by position");
  expect(operation).toHaveTextContent("Create assignment row");
  expect(operation).toHaveTextContent("Update assignment remarks");
  expect(operation).toHaveTextContent("Delete assignment row");
  await userEvent.selectOptions(operation, "assignment.create");
  await userEvent.selectOptions(
    screen.getByLabelText("Draft revision"),
    revision.id,
  );
  await userEvent.type(screen.getByLabelText("Row position"), "2");
  await userEvent.type(screen.getByLabelText("Function"), "Tactical");
  await userEvent.type(screen.getByLabelText("Channel name"), "SYN TAC");
  await userEvent.type(
    screen.getByLabelText("Assignment", { selector: "input" }),
    "Synthetic tactical assignment",
  );
  await userEvent.type(screen.getByLabelText("Remarks"), "Queued offline");
  await userEvent.click(
    screen.getByRole("button", { name: "Add to encrypted queue" }),
  );

  await waitFor(() =>
    expect(store.queueOfflineMutation).toHaveBeenCalledWith(
      editableVault,
      "synthetic passphrase",
      expect.objectContaining({
        operation: "assignment.create",
        revision_id: revision.id,
        object_id: expect.any(String),
        base_updated_at: null,
        payload: {
          position: 2,
          function: "Tactical",
          channel_name: "SYN TAC",
          assignment: "Synthetic tactical assignment",
          remarks: "Queued offline",
        },
      }),
    ),
  );
});

test("requires an explicit operator decision for a synchronization conflict", async () => {
  const active = packageFixture();
  const conflictingVault: OfflineVault = {
    ...vaultFixture(),
    mutations: [
      {
        id: "66666666-6666-4666-8666-666666666666",
        sequence: 1,
        actor_id: 7,
        device_id: active.device_id,
        operation: "revision.update",
        object_id: revision.id,
        revision_id: revision.id,
        previous_hash: active.last_chain_sha256,
        payload_sha256: "c".repeat(64),
        mutation_sha256: "d".repeat(64),
        payload: { prepared_by_position: "Sensitive local value" },
        base_updated_at: revision.updated_at ?? null,
        occurred_at_client: "2026-07-28T20:10:00Z",
        sync_status: "conflict",
        sync_result: {
          code: "stale_base_revision",
          detail: "The server revision changed after packaging.",
        },
      },
    ],
  };
  api.listOfflinePackages.mockResolvedValue([active]);
  store.listLocalPackageMetadata.mockResolvedValue([
    {
      id: active.id,
      incident: active.incident,
      status: active.status,
      expires_at: active.expires_at,
      manifest_sha256: active.manifest_sha256,
      salt_base64: "salt",
      iv_base64: "iv",
      ciphertext_base64: "ciphertext",
      updated_at: active.updated_at,
    },
  ]);
  store.unlockLocalPackage.mockResolvedValue(conflictingVault);
  api.resolveOfflineConflict.mockResolvedValue({
    id: "77777777-7777-4777-8777-777777777777",
    receipt: conflictingVault.mutations[0].id,
    decision: "discard",
    explanation: "Keep server record.",
    resolved_by: 7,
    created_at: "2026-07-28T20:20:00Z",
  });
  store.removeResolvedMutation.mockResolvedValue({
    ...conflictingVault,
    mutations: [],
  });
  render(<OfflineWorkspace incident={incident} />);

  await userEvent.selectOptions(
    await screen.findByLabelText("Package"),
    active.id,
  );
  await userEvent.type(
    screen.getByLabelText("Passphrase"),
    "synthetic passphrase",
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Unlock for this session" }),
  );
  expect(
    await screen.findByText(/server revision changed after packaging/),
  ).toBeInTheDocument();
  await userEvent.click(
    screen.getByRole("button", { name: "Keep server record" }),
  );

  await waitFor(() =>
    expect(api.resolveOfflineConflict).toHaveBeenCalledWith(active.id, {
      mutation_id: conflictingVault.mutations[0].id,
      decision: "discard",
      explanation: "Operator chose to retain the current server record.",
    }),
  );
  expect(
    await screen.findByText(/Conflict resolved by retaining the server record/),
  ).toBeInTheDocument();
});
