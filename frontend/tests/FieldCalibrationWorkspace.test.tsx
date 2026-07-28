import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { FieldCalibrationWorkspace } from "../src/FieldCalibrationWorkspace";
import type {
  CalibrationSet,
  CalibrationStatus,
  FieldObservation,
  Incident,
  RFAnalysisInputSnapshot,
} from "../src/types";

const api = vi.hoisted(() => ({
  approveCalibrationSet: vi.fn(),
  createCalibrationSet: vi.fn(),
  createFieldObservation: vi.fn(),
  getCalibrationStatus: vi.fn(),
  listCalibrationSets: vi.fn(),
  listCoverageEstimates: vi.fn(),
  listDirectionalCoverageAnalyses: vi.fn(),
  listFieldObservations: vi.fn(),
  listRFAnalysisInputSnapshots: vi.fn(),
  reviewFieldObservation: vi.fn(),
}));

vi.mock("../src/api", () => api);

const incident: Incident = {
  id: "incident-calibration-1",
  name: "Synthetic calibration exercise",
  incident_number: "SYN-CAL-1",
  status: "planning",
  operational_periods: [],
  archived_at: null,
  permissions: ["rf.view", "rf.edit", "rf.approve"],
};

const snapshots: RFAnalysisInputSnapshot[] = [
  {
    id: "rf-infrastructure",
    incident: incident.id,
    profile_version: "profile-version-infrastructure",
    profile_name: "Synthetic infrastructure",
    profile_type: "fixed",
    profile_version_number: 1,
    label: "Synthetic infrastructure input",
    input_snapshot: {},
    input_sha256: "infrastructure-digest",
    archived_at: null,
  },
  {
    id: "rf-subscriber",
    incident: incident.id,
    profile_version: "profile-version-subscriber",
    profile_name: "Synthetic portable",
    profile_type: "portable",
    profile_version_number: 1,
    label: "Synthetic portable input",
    input_snapshot: {},
    input_sha256: "subscriber-digest",
    archived_at: null,
  },
];

const calibrationStatus: CalibrationStatus = {
  algorithm: "observation-envelope",
  algorithm_version: "observation-envelope-v1-provisional",
  approved_for_operational_use: false,
  minimum_usable_observations: 3,
  ratio_bounds: { minimum: "0.250", maximum: "4.000" },
  location_rule:
    "Generalized coordinates are rounded before persistence; redacted coordinates are discarded.",
  promotion_rule:
    "A calibrated recommendation remains incident-local and is never promoted automatically.",
  disclaimer: "Provisional planning decision support only.",
};

function observation(
  overrides: Partial<FieldObservation> = {},
): FieldObservation {
  return {
    id: "observation-1",
    incident: incident.id,
    infrastructure_rf_input_snapshot: snapshots[0].id,
    infrastructure_label: snapshots[0].label,
    subscriber_rf_input_snapshot: snapshots[1].id,
    subscriber_label: snapshots[1].label,
    coverage_estimate: null,
    directional_analysis: null,
    supersedes: null,
    superseded_by: null,
    classification: "good",
    evidence_type: "measured",
    observed_from: "2026-07-28T14:00:00Z",
    observed_to: "2026-07-28T14:05:00Z",
    location_precision: "generalized",
    coordinate_reference: "EPSG:4326",
    latitude: "31.120000",
    longitude: "-97.650000",
    location_precision_m: 1000,
    direction_degrees: "45.000",
    path_distance_m: 1000,
    observer_source: "Synthetic exercise team",
    collection_method: "Scripted field check",
    environment: { terrain: "synthetic rolling" },
    measurements: {
      measured_distance_m: "1000",
      predicted_distance_m: "900",
    },
    notes: "Synthetic only",
    quality_flags: [],
    source_record_id: "",
    source_revision: "synthetic-observation-v1",
    input_snapshot: {},
    input_sha256: "observation-input-digest",
    created_by: 1,
    created_at: "2026-07-28T14:06:00Z",
    current_review_state: "pending",
    reviews: [],
    ...overrides,
  };
}

function calibrationSet(
  overrides: Partial<CalibrationSet> = {},
): CalibrationSet {
  return {
    id: "calibration-set-1",
    incident: incident.id,
    name: "Synthetic local calibration",
    version: 1,
    status: "draft",
    calculation_state: "complete",
    algorithm: calibrationStatus.algorithm,
    algorithm_version: calibrationStatus.algorithm_version,
    parameters: {
      minimum_samples: 3,
      minimum_ratio: "0.25",
      maximum_ratio: "4",
    },
    baseline_preset: "balanced",
    baseline_preset_version: "balanced-v1-provisional",
    observation_ids: ["observation-1"],
    observation_snapshot: [],
    observation_sha256: "observation-set-digest",
    recommended_preset: {
      schema_version: "incident-local-calibration-recommendation-v1",
      base_preset: "balanced",
      base_preset_version: "balanced-v1-provisional",
      distance_multiplier: "1.100",
      scope: "incident_local",
      promotion_state: "not_promoted",
      organization_default_overwritten: false,
    },
    before_after: {
      before: {
        mean_absolute_error_m: "100.000",
        mean_absolute_percentage_error: "10.000",
      },
      after: {
        mean_absolute_error_m: "10.000",
        mean_absolute_percentage_error: "1.000",
      },
    },
    warnings: [],
    exclusions: [],
    result_snapshot: {},
    result_sha256: "calibration-result-digest",
    approved_at: null,
    created_at: "2026-07-28T15:00:00Z",
    is_locked: false,
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  api.getCalibrationStatus.mockResolvedValue(calibrationStatus);
  api.listRFAnalysisInputSnapshots.mockResolvedValue(snapshots);
  api.listCoverageEstimates.mockResolvedValue([]);
  api.listDirectionalCoverageAnalyses.mockResolvedValue([]);
  api.listFieldObservations.mockResolvedValue([observation()]);
  api.listCalibrationSets.mockResolvedValue([calibrationSet()]);
  api.createFieldObservation.mockResolvedValue(
    observation({ id: "new-observation" }),
  );
  api.reviewFieldObservation.mockResolvedValue(
    observation({ current_review_state: "approved" }),
  );
  api.createCalibrationSet.mockResolvedValue(calibrationSet({ id: "new-set" }));
  api.approveCalibrationSet.mockResolvedValue(
    calibrationSet({ status: "approved", is_locked: true }),
  );
  vi.spyOn(window, "prompt").mockReturnValue("Synthetic review reason");
  vi.spyOn(window, "confirm").mockReturnValue(true);
});

test("shows provenance, review state, and transparent before-after results", async () => {
  render(<FieldCalibrationWorkspace incident={incident} />);

  expect(
    await screen.findByText("observation-envelope-v1-provisional", {
      selector: "strong",
    }),
  ).toBeInTheDocument();
  const observationTable = screen.getByRole("table", {
    name: "Field observation history",
  });
  expect(within(observationTable).getByText("pending")).toBeInTheDocument();
  await userEvent
    .setup()
    .click(
      within(observationTable).getByText("Evidence", { selector: "summary" }),
    );
  expect(
    within(observationTable).getByText("observation-input-digest"),
  ).toBeInTheDocument();

  const calibrationTable = screen.getByRole("table", {
    name: "Calibration set history",
  });
  expect(
    within(calibrationTable).getByText("1.100× distance"),
  ).toBeInTheDocument();
  expect(
    within(calibrationTable).getByText(/100.0 m → 10.0 m/),
  ).toBeInTheDocument();
  expect(
    within(calibrationTable).getByText("Incident-local · not promoted"),
  ).toBeInTheDocument();
});

test("records a redacted observation and append-only review", async () => {
  const user = userEvent.setup();
  render(<FieldCalibrationWorkspace incident={incident} />);
  await screen.findByText("observation-envelope-v1-provisional", {
    selector: "strong",
  });

  await user.selectOptions(
    screen.getByLabelText("Infrastructure RF snapshot"),
    snapshots[0].id,
  );
  await user.selectOptions(
    screen.getByLabelText("Subscriber RF snapshot"),
    snapshots[1].id,
  );
  await user.selectOptions(
    screen.getByLabelText("Location handling"),
    "redacted",
  );
  await user.type(
    screen.getByLabelText("Observer or source"),
    "Synthetic exercise team",
  );
  await user.type(
    screen.getByLabelText("Collection method"),
    "Scripted field check",
  );
  await user.type(screen.getByLabelText("Measured distance (m)"), "1000");
  await user.type(screen.getByLabelText("Predicted distance (m)"), "900");
  await user.click(
    screen.getByRole("button", { name: "Record immutable observation" }),
  );

  expect(api.createFieldObservation).toHaveBeenCalledWith(
    expect.objectContaining({
      incident: incident.id,
      infrastructure_rf_input_snapshot: snapshots[0].id,
      subscriber_rf_input_snapshot: snapshots[1].id,
      location_precision: "redacted",
      latitude: null,
      longitude: null,
      location_precision_m: null,
      measurements: {
        measured_distance_m: "1000",
        predicted_distance_m: "900",
      },
    }),
  );

  await user.click(screen.getByRole("button", { name: "Approve evidence" }));
  expect(api.reviewFieldObservation).toHaveBeenCalledWith(
    "observation-1",
    "approved",
    "Synthetic review reason",
  );
});

test("creates a versioned calibration and records approval intent", async () => {
  api.getCalibrationStatus.mockResolvedValue({
    ...calibrationStatus,
    approved_for_operational_use: true,
  });
  api.listFieldObservations.mockResolvedValue([
    observation({ current_review_state: "approved" }),
  ]);
  const user = userEvent.setup();
  render(<FieldCalibrationWorkspace incident={incident} />);
  await screen.findByText("observation-envelope-v1-provisional", {
    selector: "strong",
  });

  await user.click(
    screen.getByLabelText(/good · 1000 m measured \/ 900 m predicted/i),
  );
  await user.click(
    screen.getByRole("button", { name: "Calculate transparent comparison" }),
  );
  expect(api.createCalibrationSet).toHaveBeenCalledWith({
    incident: incident.id,
    name: "Incident-local field calibration",
    observations: ["observation-1"],
    baseline_preset: "balanced",
    baseline_preset_version: "balanced-v1-provisional",
    parameters: {
      minimum_samples: 3,
      minimum_ratio: "0.25",
      maximum_ratio: "4",
    },
  });

  await user.click(
    screen.getByRole("button", { name: "Approve and lock evidence" }),
  );
  expect(api.approveCalibrationSet).toHaveBeenCalledWith("calibration-set-1");
});
