import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { HAATWorkspace } from "../src/HAATWorkspace";
import type {
  ElevationProviderStatus,
  HAATCalculation,
  Incident,
  RFAnalysisInputSnapshot,
  RadioSite,
  SubscriberProfile,
  SubscriberProfileVersion,
} from "../src/types";

const api = vi.hoisted(() => ({
  approveHAATCalculation: vi.fn(),
  createHAATCalculation: vi.fn(),
  getElevationProviderStatus: vi.fn(),
  listHAATCalculations: vi.fn(),
  listRadioSites: vi.fn(),
  listRFAnalysisInputSnapshots: vi.fn(),
  retryHAATCalculation: vi.fn(),
}));

vi.mock("../src/api", () => api);

const incident: Incident = {
  id: "incident-1",
  name: "Synthetic terrain exercise",
  incident_number: "SYN-HAAT-1",
  status: "planning",
  operational_periods: [],
  archived_at: null,
  permissions: ["rf.view", "rf.edit", "rf.approve"],
};

const site: RadioSite = {
  id: "site-1",
  incident: incident.id,
  name: "Synthetic tower",
  description: "",
  latitude: "31.000000",
  longitude: "-97.000000",
  entered_coordinate: "31,-97",
  coordinate_format: "decimal",
  coordinate_formats: {
    decimal: "31, -97",
    ddm: "",
    dms: "",
    mgrs: "",
  },
  address: "",
  source_identity: "",
  source_retrieved_at: null,
  rings: [],
};

const profile: SubscriberProfile = {
  id: "profile-1",
  incident: incident.id,
  name: "Synthetic fixed station",
  profile_type: "fixed",
  description: "",
  archived_at: null,
};

const version: SubscriberProfileVersion = {
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
  mounting_type: "tower",
  antenna_center_agl_m: "30.000",
  antenna_center_amsl_m: null,
  haat_m: null,
  input_basis: "modeled_assumption",
  notes: "Synthetic assumptions",
  erp_calculation_path: {},
  input_snapshot: {},
  input_sha256: "",
};

const rfSnapshot: RFAnalysisInputSnapshot = {
  id: "rf-snapshot-1",
  incident: incident.id,
  profile_version: version.id,
  profile_name: profile.name,
  profile_type: profile.profile_type,
  profile_version_number: version.number,
  label: "Synthetic approved RF baseline",
  input_snapshot: {
    schema_version: 1,
    profile: {
      id: profile.id,
      incident: incident.id,
      name: profile.name,
      profile_type: profile.profile_type,
    },
    profile_version: { id: version.id, number: 1 },
    inputs: {
      antenna_center_agl_m: "30.000",
    },
  },
  input_sha256: "rf-input-digest",
  created_at: "2026-07-27T19:00:00Z",
};

function provider(
  overrides: Partial<ElevationProviderStatus> = {},
): ElevationProviderStatus {
  return {
    provider: "synthetic-offline",
    dataset_product: "ICT Toolkit deterministic terrain fixture (flat)",
    horizontal_crs: "EPSG:4326",
    vertical_crs: "SYNTHETIC:LOCAL",
    target_vertical_crs: "SYNTHETIC:LOCAL",
    resolution_m: "30.000",
    source_version: "synthetic-terrain-v1",
    license_terms_url: "",
    permitted_use: "Synthetic fixture data only.",
    coverage: { type: "synthetic" },
    source_content_sha256: "source-digest",
    offline: true,
    configured: true,
    approved: true,
    available: true,
    warning: "",
    ...overrides,
  };
}

function calculation(
  overrides: Partial<HAATCalculation> = {},
): HAATCalculation {
  return {
    id: "calculation-1",
    incident: incident.id,
    site: site.id,
    site_name: site.name,
    profile_version: version.id,
    profile_name: profile.name,
    profile_version_number: 1,
    rf_input_snapshot: rfSnapshot.id,
    rf_input_label: rfSnapshot.label,
    elevation_snapshot: "elevation-1",
    elevation: {
      id: "elevation-1",
      incident: incident.id,
      site: site.id,
      query_sha256: "query-digest",
      provider: "synthetic-offline",
      dataset_product: "ICT Toolkit deterministic terrain fixture (flat)",
      horizontal_crs: "EPSG:4326",
      vertical_crs: "SYNTHETIC:LOCAL",
      target_vertical_crs: "SYNTHETIC:LOCAL",
      resolution_m: "30.000",
      source_version: "synthetic-terrain-v1",
      source_retrieved_at: "2026-07-27T20:00:00Z",
      license_terms_url: "",
      permitted_use: "Synthetic fixture data only.",
      coverage: { type: "synthetic" },
      source_content_sha256: "source-digest",
      acquisition_state: "complete",
      current_state: "complete",
      sample_sha256: "sample-digest",
      transformation: { method: "identity" },
      warnings: ["Synthetic fixture only."],
      retrieved_at: "2026-07-27T20:00:00Z",
      stale_at: "2026-08-03T20:00:00Z",
    },
    supersedes: null,
    status: "draft",
    calculation_state: "complete",
    method: "general_radial_average_terrain",
    method_version: "haat-radial-average-v1-provisional",
    radial_count: 8,
    start_azimuth_deg: "0.000",
    sampling_interval_m: 1000,
    inner_distance_m: 3000,
    outer_distance_m: 16000,
    rounding_m: "0.100",
    antenna_agl_m: "30.000",
    site_elevation_m: "100.000",
    antenna_amsl_m: "130.000",
    average_terrain_m: "100.000",
    haat_m: "30.000",
    sample_count: 112,
    excluded_sample_count: 0,
    algorithm_snapshot: {
      method_scope: "General planning radial-average terrain method.",
    },
    exclusions: [],
    warnings: ["Synthetic fixture only."],
    result_snapshot: {},
    result_sha256: "result-digest",
    approved_at: null,
    created_at: "2026-07-27T20:00:00Z",
    is_locked: false,
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  api.getElevationProviderStatus.mockResolvedValue(provider());
  api.listRadioSites.mockResolvedValue([site]);
  api.listRFAnalysisInputSnapshots.mockResolvedValue([rfSnapshot]);
  api.listHAATCalculations.mockResolvedValue([calculation()]);
  api.createHAATCalculation.mockResolvedValue(calculation({ id: "created-2" }));
  api.retryHAATCalculation.mockResolvedValue(
    calculation({ id: "retry-2", supersedes: "calculation-1" }),
  );
  api.approveHAATCalculation.mockResolvedValue(
    calculation({
      status: "approved",
      is_locked: true,
      approved_at: "2026-07-27T21:00:00Z",
    }),
  );
  vi.spyOn(window, "confirm").mockReturnValue(true);
});

test("shows source provenance, results, warnings, retry, and approval actions", async () => {
  const user = userEvent.setup();
  render(<HAATWorkspace incident={incident} />);

  expect(
    await screen.findByText("ICT Toolkit deterministic terrain fixture (flat)"),
  ).toBeInTheDocument();
  expect(screen.getByText("approved and available")).toBeInTheDocument();
  expect(screen.getAllByText("30.000 m")).toHaveLength(2);
  expect(screen.getByText("Synthetic fixture only.")).toBeInTheDocument();

  await user.selectOptions(screen.getByLabelText("Radio site"), site.id);
  await user.selectOptions(
    screen.getByLabelText("Approved RF input snapshot with antenna AGL"),
    rfSnapshot.id,
  );
  await user.click(
    screen.getByRole("button", {
      name: "Calculate elevation and HAAT",
    }),
  );
  expect(api.createHAATCalculation).toHaveBeenCalledWith(
    expect.objectContaining({
      site: site.id,
      rf_input_snapshot: rfSnapshot.id,
      radial_count: 8,
      inner_distance_m: 3000,
      outer_distance_m: 16000,
      force_refresh: false,
    }),
  );

  const result = screen
    .getByText("Synthetic tower")
    .closest(".haat-result-card");
  expect(result).not.toBeNull();
  await user.click(
    within(result as HTMLElement).getByRole("button", {
      name: "Retry with fresh elevation data",
    }),
  );
  expect(api.retryHAATCalculation).toHaveBeenCalledWith("calculation-1");

  await user.click(
    within(result as HTMLElement).getByRole("button", {
      name: "Approve and lock result",
    }),
  );
  expect(api.approveHAATCalculation).toHaveBeenCalledWith("calculation-1");
});

test("blocks calculations when the configured source is not approved", async () => {
  api.getElevationProviderStatus.mockResolvedValue(
    provider({
      approved: false,
      available: false,
      warning: "The configured elevation source is not approved.",
    }),
  );
  render(<HAATWorkspace incident={incident} />);

  expect(
    await screen.findByText("The configured elevation source is not approved."),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("button", {
      name: "Calculate elevation and HAAT",
    }),
  ).toBeDisabled();
});

test("requires an explicit profile antenna AGL before enabling calculation", async () => {
  api.listRFAnalysisInputSnapshots.mockResolvedValue([
    {
      ...rfSnapshot,
      input_snapshot: {
        ...rfSnapshot.input_snapshot,
        inputs: { antenna_center_agl_m: null },
      },
    },
  ]);
  render(<HAATWorkspace incident={incident} />);

  expect(
    await screen.findByText(
      "Create an approved RF input snapshot whose profile version includes antenna-center AGL.",
    ),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("button", {
      name: "Calculate elevation and HAAT",
    }),
  ).toBeDisabled();
});
