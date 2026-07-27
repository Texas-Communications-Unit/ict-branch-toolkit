import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { RFProfileWorkspace } from "../src/RFProfileWorkspace";
import type {
  Incident,
  RFAnalysisInputSnapshot,
  SubscriberProfile,
  SubscriberProfileVersion,
} from "../src/types";

const api = vi.hoisted(() => ({
  approveSubscriberProfileVersion: vi.fn(),
  archiveSubscriberProfile: vi.fn(),
  copySubscriberProfileVersion: vi.fn(),
  createRFAnalysisInputSnapshot: vi.fn(),
  createSubscriberProfile: vi.fn(),
  listRFAnalysisInputSnapshots: vi.fn(),
  listSubscriberProfiles: vi.fn(),
  listSubscriberProfileVersions: vi.fn(),
  updateSubscriberProfile: vi.fn(),
  updateSubscriberProfileVersion: vi.fn(),
}));

vi.mock("../src/api", () => api);

const profile: SubscriberProfile = {
  id: "profile-1",
  incident: "incident-1",
  name: "Synthetic Portable",
  profile_type: "portable",
  description: "Synthetic test assumptions",
  archived_at: null,
};

function version(
  overrides: Partial<SubscriberProfileVersion> = {},
): SubscriberProfileVersion {
  return {
    id: "version-1",
    profile: profile.id,
    number: 1,
    status: "draft",
    is_locked: false,
    approved_at: null,
    tx_frequency_hz: null,
    rx_frequency_hz: null,
    transmitter_power_w: null,
    effective_radiated_power_w: null,
    erp_source: "unknown",
    receiver_sensitivity_dbm: null,
    antenna_model: null,
    antenna_gain_db: null,
    antenna_gain_reference: "unknown",
    feed_line_type: null,
    feed_line_length_m: null,
    feed_line_loss_db: null,
    additional_system_loss_db: null,
    polarization: "unknown",
    frequency_band: "unknown",
    emission_designator: null,
    emission_bandwidth_hz: null,
    mounting_type: "unknown",
    antenna_center_agl_m: null,
    antenna_center_amsl_m: null,
    haat_m: null,
    input_basis: "unknown",
    notes: null,
    erp_calculation_path: null,
    input_snapshot: null,
    input_sha256: null,
    ...overrides,
  };
}

function incident(permissions: string[]): Incident {
  return {
    id: "incident-1",
    name: "Synthetic Exercise",
    incident_number: "SYN-001",
    status: "planning",
    operational_periods: [],
    archived_at: null,
    permissions,
  };
}

let currentVersion: SubscriberProfileVersion;
let snapshots: RFAnalysisInputSnapshot[];

beforeEach(() => {
  vi.clearAllMocks();
  currentVersion = version();
  snapshots = [];
  api.listSubscriberProfiles.mockResolvedValue([profile]);
  api.listSubscriberProfileVersions.mockImplementation(async () => [
    currentVersion,
  ]);
  api.listRFAnalysisInputSnapshots.mockImplementation(async () => snapshots);
  api.createSubscriberProfile.mockResolvedValue(profile);
  api.updateSubscriberProfile.mockResolvedValue(profile);
  api.updateSubscriberProfileVersion.mockImplementation(
    async (_id, payload) => {
      currentVersion = { ...currentVersion, ...payload };
      return currentVersion;
    },
  );
  api.approveSubscriberProfileVersion.mockImplementation(async () => {
    currentVersion = {
      ...currentVersion,
      status: "approved",
      is_locked: true,
      approved_at: "2026-07-27T22:00:00Z",
      erp_calculation_path: {
        formula: "transmitter_power_w + gains - losses",
      },
    };
    return currentVersion;
  });
  api.copySubscriberProfileVersion.mockImplementation(async () => {
    currentVersion = version({
      id: "version-2",
      number: 2,
      transmitter_power_w: "5.2500",
    });
    return currentVersion;
  });
  api.createRFAnalysisInputSnapshot.mockImplementation(
    async (versionId, label) => {
      const snapshot: RFAnalysisInputSnapshot = {
        id: "snapshot-1",
        incident: "incident-1",
        profile_version: versionId,
        label,
        input_snapshot: { transmitter_power_w: "5.2500" },
        input_sha256: "a".repeat(64),
        created_at: "2026-07-27T22:05:00Z",
      };
      snapshots = [snapshot];
      return snapshot;
    },
  );
  api.archiveSubscriberProfile.mockResolvedValue(undefined);
});

test("creates all supported profile types and preserves exact draft values", async () => {
  const user = userEvent.setup();
  render(
    <RFProfileWorkspace
      incident={incident(["rf.view", "rf.edit", "rf.approve"])}
    />,
  );

  await screen.findByRole("option", { name: "Synthetic Portable · Portable" });
  await user.click(screen.getByText("Create subscriber profile"));
  const createDetails = screen
    .getByText("Create subscriber profile")
    .closest("details");
  expect(createDetails).not.toBeNull();
  const createForm = within(createDetails!);
  const profileType = createForm.getByLabelText("Profile type");
  expect(
    within(profileType).getByRole("option", { name: "Portable" }),
  ).toBeInTheDocument();
  expect(
    within(profileType).getByRole("option", { name: "Mobile" }),
  ).toBeInTheDocument();
  expect(
    within(profileType).getByRole("option", { name: "Fixed" }),
  ).toBeInTheDocument();
  expect(
    within(profileType).getByRole("option", { name: "Configurable" }),
  ).toBeInTheDocument();

  await user.type(createForm.getByLabelText("Profile name"), "Local custom");
  await user.selectOptions(profileType, "configurable");
  await user.type(
    createForm.getByLabelText("Description"),
    "Synthetic values only",
  );
  await user.click(
    createForm.getByRole("button", {
      name: "Create profile and draft",
    }),
  );

  await waitFor(() =>
    expect(api.createSubscriberProfile).toHaveBeenCalledWith(
      expect.objectContaining({
        incident: "incident-1",
        name: "Local custom",
        profile_type: "configurable",
        description: "Synthetic values only",
        initial_version: expect.objectContaining({
          tx_frequency_hz: null,
          transmitter_power_w: null,
          antenna_center_agl_m: null,
          erp_source: "unknown",
          input_basis: "unknown",
        }),
      }),
    ),
  );
  const initialVersion =
    api.createSubscriberProfile.mock.calls[0][0].initial_version;
  expect(initialVersion).not.toHaveProperty("erp_calculation_path");
  expect(initialVersion).not.toHaveProperty("input_snapshot");
  expect(initialVersion).not.toHaveProperty("input_sha256");

  await user.type(
    screen.getByLabelText("Transmit frequency (Hz)"),
    "155000000",
  );
  await user.type(screen.getByLabelText("Transmitter power (W)"), "5.2500");
  const erpSource = screen.getByLabelText("ERP source");
  expect(erpSource).toBeInstanceOf(HTMLSelectElement);
  expect(
    within(erpSource).getByRole("option", {
      name: "Unknown (controlled value)",
    }),
  ).toHaveValue("unknown");
  await user.selectOptions(erpSource, "entered");
  await user.type(screen.getByLabelText("Antenna center AGL (m)"), "12.50");
  await user.click(screen.getByRole("button", { name: "Save RF draft" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Notes are required when ERP source is Entered directly.",
  );
  expect(api.updateSubscriberProfileVersion).not.toHaveBeenCalled();

  await user.type(
    screen.getByLabelText("Notes"),
    "Synthetic entered ERP fixture",
  );
  await user.click(screen.getByRole("button", { name: "Save RF draft" }));

  await waitFor(() =>
    expect(api.updateSubscriberProfileVersion).toHaveBeenCalledWith(
      "version-1",
      expect.objectContaining({
        tx_frequency_hz: 155000000,
        rx_frequency_hz: null,
        transmitter_power_w: "5.2500",
        erp_source: "entered",
        antenna_center_agl_m: "12.50",
        notes: "Synthetic entered ERP fixture",
      }),
    ),
  );

  await user.clear(screen.getByLabelText("Notes"));
  await user.selectOptions(screen.getByLabelText("Input basis"), "mixed");
  await user.click(screen.getByRole("button", { name: "Save RF draft" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Notes are required when ERP source is Entered directly and when input basis is Mixed facts and assumptions.",
  );
  expect(api.updateSubscriberProfileVersion).toHaveBeenCalledTimes(1);
});

test("confirms approval and archive actions and creates immutable snapshots", async () => {
  const user = userEvent.setup();
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
  render(
    <RFProfileWorkspace
      incident={incident(["rf.view", "rf.edit", "rf.approve"])}
    />,
  );

  await user.click(
    await screen.findByRole("button", {
      name: "Approve and lock RF version",
    }),
  );
  expect(confirm).toHaveBeenCalledWith(
    "Approve and lock version 1? Later changes require a copied draft.",
  );
  await screen.findByText("Server calculation path and immutable provenance");

  await user.type(
    screen.getByLabelText("Snapshot label"),
    "Synthetic baseline",
  );
  await user.click(
    screen.getByRole("button", { name: "Create immutable snapshot" }),
  );
  expect(api.createRFAnalysisInputSnapshot).toHaveBeenCalledWith(
    "version-1",
    "Synthetic baseline",
  );
  expect(await screen.findByText("Synthetic baseline")).toBeInTheDocument();
  expect(screen.getByText("a".repeat(64))).toBeInTheDocument();

  await user.click(
    screen.getByRole("button", {
      name: "Copy approved version to new draft",
    }),
  );
  expect(await screen.findByText("Version 2")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Archive profile" }));
  expect(confirm).toHaveBeenCalledWith(
    "Archive Synthetic Portable? Its versions and audit history will be retained.",
  );
  expect(api.archiveSubscriberProfile).toHaveBeenCalledWith("profile-1");
});

test("renders incident RF data as read-only without edit or approval access", async () => {
  render(<RFProfileWorkspace incident={incident(["rf.view"])} />);

  const transmitFrequency = await screen.findByLabelText(
    "Transmit frequency (Hz)",
  );
  expect(transmitFrequency).toHaveAttribute("readonly");
  expect(
    screen.queryByText("Create subscriber profile"),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Save RF draft" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Approve and lock RF version" }),
  ).not.toBeInTheDocument();
  expect(screen.getByText("Unknown values:").closest("p")).toHaveTextContent(
    /a blank nullable measurement or text field is sent as null and means explicitly unknown/i,
  );
});
