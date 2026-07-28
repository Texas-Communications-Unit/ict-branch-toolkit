import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { CoverageEstimateWorkspace } from "../src/CoverageEstimateWorkspace";
import type {
  CoverageEngineStatus,
  CoverageEstimate,
  HAATCalculation,
  Incident,
} from "../src/types";

const api = vi.hoisted(() => ({
  approveCoverageEstimate: vi.fn(),
  createCoverageEstimate: vi.fn(),
  getCoverageEngineStatus: vi.fn(),
  listCoverageEstimates: vi.fn(),
  listHAATCalculations: vi.fn(),
}));

vi.mock("../src/api", () => api);

const incident: Incident = {
  id: "incident-coverage-1",
  name: "Synthetic coverage exercise",
  incident_number: "SYN-COVERAGE-1",
  status: "planning",
  operational_periods: [],
  archived_at: null,
  permissions: ["rf.view", "rf.edit", "rf.approve"],
};

const engine: CoverageEngineStatus = {
  engine: "provisional_fspl_horizon",
  engine_version: "fspl-horizon-v1-provisional",
  approved_for_operational_use: false,
  approved_presets: [],
  disclaimer:
    "Provisional planning estimate only—not a propagation study, frequency-coordination decision, spectrum authorization, or coverage guarantee.",
  supported_band_groups: [
    { name: "vhf_high", lower_hz: 136_000_000, upper_hz: 174_000_000 },
  ],
  environments: [
    { name: "open", additional_margin_db: "6" },
    { name: "suburban", additional_margin_db: "16" },
  ],
  presets: {
    balanced: {
      version: "balanced-v1-provisional",
      fade_margin_db: "12",
      uncertainty_db: "6",
      receiver_height_m: "1.5",
      maximum_distance_m: 100_000,
      distance_rounding_m: 100,
    },
  },
};

const haat: HAATCalculation = {
  id: "haat-approved-1",
  incident: incident.id,
  site: "site-1",
  site_name: "Synthetic tower",
  profile_version: "profile-version-1",
  profile_name: "Synthetic fixed station",
  profile_version_number: 1,
  rf_input_snapshot: "rf-snapshot-1",
  rf_input_label: "Synthetic approved RF input",
  elevation_snapshot: "elevation-1",
  elevation: {
    id: "elevation-1",
    incident: incident.id,
    site: "site-1",
    query_sha256: "query-digest",
    provider: "synthetic-offline",
    dataset_product: "Synthetic flat terrain",
    horizontal_crs: "EPSG:4326",
    vertical_crs: "SYNTHETIC:LOCAL",
    target_vertical_crs: "SYNTHETIC:LOCAL",
    resolution_m: "30.000",
    source_version: "synthetic-v1",
    source_retrieved_at: "2026-07-28T01:00:00Z",
    license_terms_url: "",
    permitted_use: "Synthetic tests only.",
    coverage: { type: "synthetic" },
    source_content_sha256: "source-digest",
    acquisition_state: "complete",
    current_state: "complete",
    sample_sha256: "sample-digest",
    transformation: {},
    warnings: [],
    retrieved_at: "2026-07-28T01:00:00Z",
    stale_at: null,
  },
  supersedes: null,
  status: "approved",
  calculation_state: "complete",
  method: "general_radial_average_terrain",
  method_version: "haat-radial-average-v1-provisional",
  radial_count: 8,
  start_azimuth_deg: "0.000",
  sampling_interval_m: 1000,
  inner_distance_m: 3000,
  outer_distance_m: 16_000,
  rounding_m: "0.100",
  antenna_agl_m: "30.000",
  site_elevation_m: "100.000",
  antenna_amsl_m: "130.000",
  average_terrain_m: "100.000",
  haat_m: "30.000",
  sample_count: 112,
  excluded_sample_count: 0,
  algorithm_snapshot: {},
  exclusions: [],
  warnings: [],
  result_snapshot: {},
  result_sha256: "haat-result-digest",
  approved_at: "2026-07-28T01:00:00Z",
  created_at: "2026-07-28T01:00:00Z",
  is_locked: true,
};

function estimate(overrides: Partial<CoverageEstimate> = {}): CoverageEstimate {
  return {
    id: "estimate-1",
    incident: incident.id,
    site: "site-1",
    site_name: "Synthetic tower",
    rf_input_snapshot: "rf-snapshot-1",
    rf_input_label: "Synthetic approved RF input",
    haat_calculation: haat.id,
    haat_result_sha256: haat.result_sha256,
    status: "draft",
    calculation_state: "complete",
    environment: "suburban",
    band: "vhf_high",
    engine: engine.engine,
    engine_version: engine.engine_version,
    preset: "balanced",
    preset_version: "balanced-v1-provisional",
    center_latitude: "31.000000",
    center_longitude: "-97.000000",
    nominal_distance_m: 24_000,
    conservative_distance_m: 12_000,
    optimistic_distance_m: 36_000,
    input_snapshot: {},
    input_sha256: "input-digest",
    model_snapshot: {},
    warnings: [engine.disclaimer],
    exclusions: [],
    explanation:
      "The provisional engine applied the suburban margin and balanced preset.",
    result_snapshot: {},
    result_sha256: "estimate-result-digest",
    approved_at: null,
    created_at: "2026-07-28T02:00:00Z",
    is_locked: false,
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  api.getCoverageEngineStatus.mockResolvedValue(engine);
  api.listHAATCalculations.mockResolvedValue([haat]);
  api.listCoverageEstimates.mockResolvedValue([estimate()]);
  api.createCoverageEstimate.mockResolvedValue(estimate({ id: "estimate-2" }));
  api.approveCoverageEstimate.mockResolvedValue(
    estimate({
      status: "approved",
      approved_at: "2026-07-28T03:00:00Z",
      is_locked: true,
    }),
  );
  vi.spyOn(window, "confirm").mockReturnValue(true);
});

test("shows assumptions, accessible distance table, and evidence", async () => {
  render(<CoverageEstimateWorkspace incident={incident} />);

  expect(
    await screen.findByText("fspl-horizon-v1-provisional", {
      selector: "strong",
    }),
  ).toBeInTheDocument();
  expect(
    screen.getByText("Provisional configuration—practitioner review required"),
  ).toBeInTheDocument();
  const table = screen.getByRole("table", { name: /provisional results/i });
  expect(within(table).getByText("12.0 km")).toBeInTheDocument();
  expect(within(table).getByText("24.0 km")).toBeInTheDocument();
  expect(within(table).getByText("36.0 km")).toBeInTheDocument();

  await userEvent
    .setup()
    .click(within(table).getByText("Explanation and digests"));
  expect(within(table).getByText("input-digest")).toBeInTheDocument();
  expect(within(table).getByText("haat-result-digest")).toBeInTheDocument();
  expect(within(table).getByText("estimate-result-digest")).toBeInTheDocument();
});

test("creates and approves a provisional estimate", async () => {
  api.getCoverageEngineStatus.mockResolvedValue({
    ...engine,
    approved_for_operational_use: true,
    approved_presets: [
      {
        preset: "balanced",
        preset_version: "balanced-v1-provisional",
      },
    ],
  });
  const user = userEvent.setup();
  render(<CoverageEstimateWorkspace incident={incident} />);

  await screen.findByText("fspl-horizon-v1-provisional", {
    selector: "strong",
  });
  await user.selectOptions(
    screen.getByLabelText("Approved HAAT calculation"),
    haat.id,
  );
  await user.selectOptions(
    screen.getByLabelText("Operating environment"),
    "open",
  );
  await user.click(
    screen.getByRole("button", { name: "Create explainable estimate" }),
  );
  expect(api.createCoverageEstimate).toHaveBeenCalledWith({
    haat_calculation: haat.id,
    environment: "open",
    preset: "balanced",
  });

  await user.click(screen.getByText("Explanation and digests"));
  await user.click(
    screen.getByRole("button", { name: "Approve and lock estimate" }),
  );
  expect(api.approveCoverageEstimate).toHaveBeenCalledWith("estimate-1");
});

test("requires approved complete HAAT evidence", async () => {
  api.listHAATCalculations.mockResolvedValue([
    { ...haat, status: "draft", is_locked: false, approved_at: null },
  ]);
  render(<CoverageEstimateWorkspace incident={incident} />);

  expect(
    await screen.findByText(
      "Approve a complete HAAT calculation before creating an estimate.",
    ),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "Create explainable estimate" }),
  ).toBeDisabled();
});
