import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { DirectionalCoverageWorkspace } from "../src/DirectionalCoverageWorkspace";
import type {
  CoverageEngineStatus,
  DirectionalAnalysisStatus,
  DirectionalCoverageAnalysis,
  HAATCalculation,
  Incident,
  RFAnalysisInputSnapshot,
} from "../src/types";

const api = vi.hoisted(() => ({
  approveDirectionalCoverageAnalysis: vi.fn(),
  createDirectionalCoverageAnalysis: vi.fn(),
  getCoverageEngineStatus: vi.fn(),
  getDirectionalAnalysisStatus: vi.fn(),
  listDirectionalCoverageAnalyses: vi.fn(),
  listHAATCalculations: vi.fn(),
  listRFAnalysisInputSnapshots: vi.fn(),
}));

vi.mock("../src/api", () => api);

const incident: Incident = {
  id: "incident-directional-1",
  name: "Synthetic directional exercise",
  incident_number: "SYN-DIRECTIONAL-1",
  status: "planning",
  operational_periods: [],
  archived_at: null,
  permissions: ["rf.view", "rf.edit", "rf.approve"],
};

const engine: CoverageEngineStatus = {
  engine: "provisional_fspl_horizon",
  engine_version: "fspl-horizon-v1-provisional",
  approved_for_operational_use: true,
  approved_presets: [
    { preset: "balanced", preset_version: "balanced-v1-provisional" },
  ],
  disclaimer: "Provisional planning estimate only—not a coverage guarantee.",
  supported_band_groups: [
    { name: "vhf_high", lower_hz: 136_000_000, upper_hz: 174_000_000 },
  ],
  environments: [{ name: "suburban", additional_margin_db: "16" }],
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

const directionalStatus: DirectionalAnalysisStatus = {
  rule_version: "concentric-minimum-v1-provisional",
  approved_for_operational_use: true,
  rule: "Probable two-way distance is the smaller supported nominal path.",
  disclaimer: engine.disclaimer,
  supported_profile_types: [
    "portable",
    "mobile",
    "fixed",
    "cache",
    "gateway",
    "configurable",
  ],
};

const haat = {
  id: "haat-1",
  incident: incident.id,
  site: "site-1",
  site_name: "Synthetic tower",
  rf_input_snapshot: "infrastructure-snapshot",
  rf_input_label: "Synthetic infrastructure",
  status: "approved",
  calculation_state: "complete",
  haat_m: "30.000",
  result_sha256: "haat-digest",
  is_locked: true,
} as HAATCalculation;

const subscriber: RFAnalysisInputSnapshot = {
  id: "subscriber-snapshot",
  incident: incident.id,
  profile_version: "subscriber-version",
  profile_name: "Portable team",
  profile_type: "portable",
  profile_version_number: 1,
  label: "Synthetic portable input",
  input_snapshot: {},
  input_sha256: "subscriber-digest",
  created_at: "2026-07-28T05:00:00Z",
};

function analysis(
  overrides: Partial<DirectionalCoverageAnalysis> = {},
): DirectionalCoverageAnalysis {
  return {
    id: "directional-1",
    incident: incident.id,
    site: "site-1",
    site_name: "Synthetic tower",
    infrastructure_rf_input_snapshot: "infrastructure-snapshot",
    infrastructure_label: "Synthetic infrastructure",
    subscriber_rf_input_snapshot: subscriber.id,
    subscriber_label: subscriber.label,
    subscriber_profile_name: subscriber.profile_name,
    subscriber_profile_type: subscriber.profile_type,
    haat_calculation: haat.id,
    haat_result_sha256: haat.result_sha256,
    status: "draft",
    calculation_state: "complete",
    environment: "suburban",
    engine: engine.engine,
    engine_version: engine.engine_version,
    preset: "balanced",
    preset_version: "balanced-v1-provisional",
    rule_version: directionalStatus.rule_version,
    center_latitude: "31.000000",
    center_longitude: "-97.000000",
    talk_out_distance_m: 24_000,
    talk_in_distance_m: 8_000,
    probable_two_way_distance_m: 8_000,
    limiting_path: "talk_in",
    input_snapshot: {},
    input_sha256: "directional-input-digest",
    model_snapshot: {},
    warnings: [engine.disclaimer],
    exclusions: [],
    explanation: "Talk-in is the limiting path.",
    result_snapshot: {},
    result_sha256: "directional-result-digest",
    approved_at: null,
    created_at: "2026-07-28T06:00:00Z",
    is_locked: false,
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  api.getCoverageEngineStatus.mockResolvedValue(engine);
  api.getDirectionalAnalysisStatus.mockResolvedValue(directionalStatus);
  api.listHAATCalculations.mockResolvedValue([haat]);
  api.listRFAnalysisInputSnapshots.mockResolvedValue([subscriber]);
  api.listDirectionalCoverageAnalyses.mockResolvedValue([analysis()]);
  api.createDirectionalCoverageAnalysis.mockResolvedValue(
    analysis({ id: "directional-2" }),
  );
  api.approveDirectionalCoverageAnalysis.mockResolvedValue(
    analysis({ status: "approved", is_locked: true }),
  );
  vi.spyOn(window, "confirm").mockReturnValue(true);
});

test("shows separate directional paths, limiting path, and evidence", async () => {
  render(<DirectionalCoverageWorkspace incident={incident} />);

  expect(
    await screen.findByText("concentric-minimum-v1-provisional", {
      selector: "strong",
    }),
  ).toBeInTheDocument();
  const table = screen.getByRole("table", { name: /separate nominal path/i });
  expect(within(table).getByText("24.0 km")).toBeInTheDocument();
  expect(within(table).getAllByText("8.0 km")).toHaveLength(2);
  expect(within(table).getByText("talk in")).toBeInTheDocument();

  await userEvent
    .setup()
    .click(within(table).getByText("Explanation and digests"));
  expect(
    within(table).getByText("directional-input-digest"),
  ).toBeInTheDocument();
  expect(
    within(table).getByText("directional-result-digest"),
  ).toBeInTheDocument();
});

test("creates and approves a directional analysis", async () => {
  const user = userEvent.setup();
  render(<DirectionalCoverageWorkspace incident={incident} />);

  await screen.findByText("concentric-minimum-v1-provisional", {
    selector: "strong",
  });
  await user.selectOptions(
    screen.getByLabelText("Approved infrastructure HAAT"),
    haat.id,
  );
  await user.selectOptions(
    screen.getByLabelText("Approved subscriber input"),
    subscriber.id,
  );
  await user.click(
    screen.getByRole("button", { name: "Calculate separate paths" }),
  );
  expect(api.createDirectionalCoverageAnalysis).toHaveBeenCalledWith({
    haat_calculation: haat.id,
    subscriber_rf_input_snapshot: subscriber.id,
    environment: "suburban",
    preset: "balanced",
  });

  await user.click(screen.getByText("Explanation and digests"));
  await user.click(
    screen.getByRole("button", {
      name: "Approve and lock directional analysis",
    }),
  );
  expect(api.approveDirectionalCoverageAnalysis).toHaveBeenCalledWith(
    "directional-1",
  );
});

test("keeps approval disabled when the directional rule is not approved", async () => {
  api.getDirectionalAnalysisStatus.mockResolvedValue({
    ...directionalStatus,
    approved_for_operational_use: false,
  });
  render(<DirectionalCoverageWorkspace incident={incident} />);

  await screen.findByText("concentric-minimum-v1-provisional", {
    selector: "strong",
  });
  await userEvent.setup().click(screen.getByText("Explanation and digests"));
  expect(
    screen.queryByRole("button", {
      name: "Approve and lock directional analysis",
    }),
  ).not.toBeInTheDocument();
  expect(
    screen.getByText(
      /have not all passed their configured practitioner gates/i,
    ),
  ).toBeInTheDocument();
});
