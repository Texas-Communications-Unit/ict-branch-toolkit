import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ExtensionWorkspace } from "../src/ExtensionWorkspace";
import type {
  CurrentUser,
  ExtensionCatalogEntry,
  ExtensionExecution,
  ICS205Plan,
  Incident,
} from "../src/types";

const api = vi.hoisted(() => ({
  createExtensionExecution: vi.fn(),
  disableExtension: vi.fn(),
  downloadExtensionExecution: vi.fn(),
  enableExtension: vi.fn(),
  installExtension: vi.fn(),
  listExtensionCatalog: vi.fn(),
  listExtensionExecutions: vi.fn(),
  listPlans: vi.fn(),
}));

vi.mock("../src/api", () => api);

const incident: Incident = {
  id: "incident-extension-1",
  name: "Synthetic Extension Exercise",
  incident_number: "SYN-EXT-1",
  status: "planning",
  operational_periods: [],
  archived_at: null,
  permissions: ["extension.view", "extension.run"],
};

const administrator: CurrentUser = {
  username: "extension-admin",
  display_name: "Extension Administrator",
  role: "administrator",
  permissions: ["extension.view", "extension.run", "extension.admin"],
};

const catalogEntry: ExtensionCatalogEntry = {
  manifest: {
    key: "synthetic-readiness-summary",
    name: "Synthetic readiness summary",
    description: "A non-operational contract example.",
    version: "1.0.0",
    contract_version: "1.0",
    provider: "ICT Branch Toolkit built-in synthetic example",
    capabilities: [
      {
        id: "readiness-check",
        name: "Synthetic readiness check",
        kind: "tool",
        required_permission: "extension.run",
        scope: "incident_revision",
        inputs: {},
        outputs: {
          schema: "synthetic-readiness-tool-v1",
          classification: "decision_support",
        },
        validation: "Approved revision required.",
        audit: "Digests retained.",
        export: { formats: ["json"], deterministic: true },
      },
      {
        id: "readiness-report",
        name: "Synthetic readiness report",
        kind: "report",
        required_permission: "extension.run",
        scope: "incident_revision",
        inputs: {},
        outputs: {
          schema: "synthetic-readiness-report-v1",
          classification: "decision_support",
        },
        validation: "Approved revision required.",
        audit: "Digests retained.",
        export: { formats: ["json"], deterministic: true },
      },
    ],
    source_records: ["Approved ICS-205 assignment metadata and counts."],
    approval_requirements: "Never an official approval.",
    sensitivity: "internal_incident_metadata",
    retention: "Retain with the incident; no automatic purge.",
    failure_isolation: "Failure cannot change source records.",
    accessibility: "Structured text and JSON.",
    official_output: false,
  },
  installed: false,
  enabled: false,
  compatible: false,
  installation_id: null,
  operator_message:
    "Not installed. An administrator must install and enable this extension.",
};

const plan: ICS205Plan = {
  id: "plan-extension-1",
  incident: incident.id,
  operational_period: "period-extension-1",
  title: "Synthetic ICS-205",
  revisions: [
    {
      id: "revision-extension-1",
      plan: "plan-extension-1",
      number: 1,
      status: "approved",
      is_locked: true,
      prepared_by_name: "Synthetic COML",
      prepared_by_position: "COML",
      copied_from: null,
      approved_at: "2026-07-28T20:00:00Z",
      collaboration_version: 1,
      assignments: [],
      relationships: [],
    },
  ],
};

const execution: ExtensionExecution = {
  id: "execution-extension-1",
  extension_key: catalogEntry.manifest.key,
  extension_version: "1.0.0",
  contract_version: "1.0",
  capability: "readiness-report",
  capability_kind: "report",
  incident: incident.id,
  source_revision: "revision-extension-1",
  source_revision_number: 1,
  input_snapshot: {},
  input_sha256: "a".repeat(64),
  result_snapshot: {
    schema_version: "synthetic-readiness-report-v1",
    summary: {
      readiness_state: "attention",
      assignment_count: 2,
      missing_frequency_count: 1,
    },
    columns: ["Function", "Assignment count"],
    rows: [
      ["Command", 1],
      ["Operations", 1],
    ],
  },
  result_sha256: "b".repeat(64),
  output_classification: "decision_support",
  status: "complete",
  failure_code: "",
  failure_message: "",
  created_by: 1,
  created_at: "2026-07-28T21:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
  api.listExtensionCatalog.mockResolvedValue([catalogEntry]);
  api.listPlans.mockResolvedValue([plan]);
  api.listExtensionExecutions.mockResolvedValue([]);
  api.installExtension.mockResolvedValue(undefined);
  api.enableExtension.mockResolvedValue(undefined);
  api.disableExtension.mockResolvedValue(undefined);
  api.createExtensionExecution.mockResolvedValue(execution);
  api.downloadExtensionExecution.mockResolvedValue(undefined);
});

test("shows the governed contract and lets only an administrator install it disabled", async () => {
  api.listExtensionCatalog
    .mockResolvedValueOnce([catalogEntry])
    .mockResolvedValue([
      {
        ...catalogEntry,
        installed: true,
        compatible: true,
        operator_message: "Installed but disabled.",
      },
    ]);
  const user = userEvent.setup();
  render(
    <ExtensionWorkspace incident={incident} currentUser={administrator} />,
  );

  expect(
    await screen.findByRole("heading", {
      name: "Synthetic readiness summary",
    }),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/Arbitrary uploaded executable code is not supported/i),
  ).toBeInTheDocument();
  await user.click(screen.getByText("Contract, governance, and retention"));
  expect(screen.getByText(/no automatic purge/i)).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Install disabled" }));
  expect(api.installExtension).toHaveBeenCalledWith(
    catalogEntry.manifest.key,
    "1.0",
  );
  expect(
    await screen.findByRole("button", {
      name: "Enable compatible version",
    }),
  ).toBeInTheDocument();
});

test("runs an enabled report, presents structured output, and downloads deterministic JSON", async () => {
  api.listExtensionCatalog.mockResolvedValue([
    {
      ...catalogEntry,
      installed: true,
      enabled: true,
      compatible: true,
      installation_id: "installation-extension-1",
      operator_message: "Installed, enabled, and contract-compatible.",
    },
  ]);
  api.listExtensionExecutions
    .mockResolvedValueOnce([])
    .mockResolvedValue([execution]);
  const user = userEvent.setup();
  render(
    <ExtensionWorkspace incident={incident} currentUser={administrator} />,
  );

  await screen.findByRole("heading", {
    name: "Run the synthetic contract example",
  });
  await user.selectOptions(
    screen.getByLabelText("Capability"),
    "readiness-report",
  );
  await user.selectOptions(
    screen.getByLabelText("Approved ICS-205 revision"),
    "revision-extension-1",
  );
  await user.clear(screen.getByLabelText("Minimum assignment count"));
  await user.type(screen.getByLabelText("Minimum assignment count"), "2");
  await user.click(
    screen.getByRole("button", { name: "Run synthetic extension" }),
  );

  expect(api.createExtensionExecution).toHaveBeenCalledWith({
    extension_key: catalogEntry.manifest.key,
    contract_version: "1.0",
    capability: "readiness-report",
    incident: incident.id,
    source_revision: "revision-extension-1",
    inputs: { minimum_assignment_count: 2 },
  });
  expect(
    await screen.findByRole("table", {
      name: "Synthetic assignment counts by function",
    }),
  ).toBeInTheDocument();
  expect(screen.getByText("attention")).toBeInTheDocument();
  await user.click(
    screen.getByRole("button", { name: "Download deterministic JSON" }),
  );
  expect(api.downloadExtensionExecution).toHaveBeenCalledWith(execution);
});

test("does not expose administrator controls to a non-administrator", async () => {
  render(
    <ExtensionWorkspace
      incident={incident}
      currentUser={{
        ...administrator,
        role: "coml",
        permissions: ["extension.view", "extension.run"],
      }}
    />,
  );
  await screen.findByRole("heading", {
    name: "Synthetic readiness summary",
  });
  expect(
    screen.queryByRole("button", { name: "Install disabled" }),
  ).not.toBeInTheDocument();
});
