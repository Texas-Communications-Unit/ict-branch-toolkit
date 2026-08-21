import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { Phase2ValidationWorkspace } from "../src/Phase2ValidationWorkspace";
import type {
  CalibrationSet,
  CoverageEstimate,
  DirectionalCoverageAnalysis,
  HAATCalculation,
  ICS205Plan,
  Incident,
  Phase2ValidationBundle,
  Phase2ValidationStatus,
} from "../src/types";

const api = vi.hoisted(() => ({
  approvePhase2ValidationBundle: vi.fn(),
  cancelPhase2ValidationBundle: vi.fn(),
  createPhase2ValidationBundle: vi.fn(),
  downloadPhase2ValidationBundle: vi.fn(),
  getPhase2ValidationStatus: vi.fn(),
  listCalibrationSets: vi.fn(),
  listCoverageEstimates: vi.fn(),
  listDirectionalCoverageAnalyses: vi.fn(),
  listHAATCalculations: vi.fn(),
  listPhase2ValidationBundles: vi.fn(),
  listPlans: vi.fn(),
  retryPhase2ValidationBundle: vi.fn(),
  runPhase2ValidationBundle: vi.fn(),
  verifyPhase2ValidationExport: vi.fn(),
}));

vi.mock("../src/api", () => api);

const incident: Incident = {
  id: "incident-p2",
  name: "Synthetic Phase 2 exercise",
  incident_number: "SYN-P2",
  status: "planning",
  operational_periods: [],
  archived_at: null,
  permissions: ["rf.view", "rf.edit", "rf.approve", "plan.export"],
};

const validationStatus: Phase2ValidationStatus = {
  validation_profile_id: "phase-2-validation",
  validation_profile_version: "phase-2-validation-v1-provisional",
  validation_method_version:
    "deterministic-distance-ratio-comparison-v1-provisional",
  approved_for_release_candidate_use: true,
  execution_model: "explicit synchronous staged job",
  cancellation_boundary:
    "Queued work can be cancelled before explicit execution.",
  classification: "NON-PRODUCTION PHASE 2 VALIDATION EVIDENCE",
  resource_safety_limits: {
    maximum_plan_assignments: 1000,
    maximum_calibration_observations: 1000,
    maximum_verification_upload_bytes: 10485760,
  },
  disclaimer: "Deterministic software evidence only.",
};

const plan: ICS205Plan = {
  id: "plan-1",
  incident: incident.id,
  operational_period: "period-1",
  title: "Incident Radio Communications Plan",
  revisions: [
    {
      id: "revision-1",
      plan: "plan-1",
      number: 1,
      status: "approved",
      is_locked: true,
      prepared_by_name: "Synthetic planner",
      prepared_by_position: "COML",
      copied_from: null,
      approved_at: "2026-07-28T12:00:00Z",
      collaboration_version: 1,
      assignments: [
        {
          id: "assignment-1",
          revision: "revision-1",
          position: 1,
          function: "Command",
          channel_name: "SYN CALL",
          assignment: "Synthetic",
          operating_classification: "fixed_pair",
          technology_subtype: "",
          subscriber_profile_version: null,
          rx_frequency_hz: 155000000,
          rx_channel_width_hz: 12500,
          rx_squelch: "CSQ",
          tx_frequency_hz: 155000000,
          tx_channel_width_hz: 12500,
          tx_squelch: "CSQ",
          mode: "analog_fm",
          remarks: "",
          structured_note: "",
          contact_name: "",
          site_address: "",
          phone_numbers: "",
          contact_24_hour: "",
          published_contact_fields: [],
          contact_publication_purpose: "",
          contact_publication_placement: "remarks",
          collaboration_version: 1,
          resource_snapshot: {},
        },
      ],
      relationships: [],
    },
  ],
};

const haat = {
  id: "haat-1",
  incident: incident.id,
  site_name: "Synthetic site",
  status: "approved",
  calculation_state: "complete",
  haat_m: "30.000",
  result_sha256: "a".repeat(64),
} as HAATCalculation;

const coverage = {
  id: "coverage-1",
  incident: incident.id,
  site_name: "Synthetic site",
  status: "approved",
  calculation_state: "complete",
  environment: "suburban",
  nominal_distance_m: 10000,
} as CoverageEstimate;

const directional = {
  id: "directional-1",
  incident: incident.id,
  site_name: "Synthetic site",
  status: "approved",
  calculation_state: "complete",
  probable_two_way_distance_m: 8000,
} as DirectionalCoverageAnalysis;

const calibration = {
  id: "calibration-1",
  incident: incident.id,
  name: "Synthetic local calibration",
  version: 1,
  status: "approved",
  calculation_state: "complete",
  observation_ids: ["observation-1", "observation-2", "observation-3"],
} as CalibrationSet;

function bundle(
  overrides: Partial<Phase2ValidationBundle> = {},
): Phase2ValidationBundle {
  return {
    id: "bundle-1",
    incident: incident.id,
    approved_revision: "revision-1",
    haat_calculation: haat.id,
    coverage_estimate: coverage.id,
    directional_analysis: directional.id,
    calibration_set: calibration.id,
    supersedes: null,
    validation_profile_id: validationStatus.validation_profile_id,
    validation_profile_version: validationStatus.validation_profile_version,
    app_version: "0.2.0-rc.1",
    job_state: "complete",
    progress_step: "complete",
    progress_percent: 100,
    status: "draft",
    input_snapshot: {},
    input_sha256: "b".repeat(64),
    result_snapshot: {
      deterministic_observation_comparison: {
        counts: {
          within_tolerance: 3,
          outside_tolerance: 0,
          not_comparable: 0,
        },
      },
      sensitivity: {
        coverage_distance_m: {
          conservative: 8000,
          nominal: 10000,
          optimistic: 12000,
        },
        directional_distance_m: {
          talk_out: 9000,
          talk_in: 8000,
          probable_two_way: 8000,
        },
      },
    },
    result_sha256: "c".repeat(64),
    failure_code: "",
    failure_message: "",
    created_by: 1,
    approved_by: null,
    created_at: "2026-07-28T13:00:00Z",
    started_at: "2026-07-28T13:01:00Z",
    completed_at: "2026-07-28T13:02:00Z",
    approved_at: null,
    updated_at: "2026-07-28T13:02:00Z",
    is_locked: false,
    is_stale: false,
    stale_reasons: [],
    approval_eligible: true,
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  api.getPhase2ValidationStatus.mockResolvedValue(validationStatus);
  api.listPlans.mockResolvedValue([plan]);
  api.listHAATCalculations.mockResolvedValue([haat]);
  api.listCoverageEstimates.mockResolvedValue([coverage]);
  api.listDirectionalCoverageAnalyses.mockResolvedValue([directional]);
  api.listCalibrationSets.mockResolvedValue([calibration]);
  api.listPhase2ValidationBundles.mockResolvedValue([bundle()]);
  api.createPhase2ValidationBundle.mockResolvedValue(
    bundle({ id: "queued-bundle", job_state: "queued", progress_percent: 0 }),
  );
  api.runPhase2ValidationBundle.mockResolvedValue(bundle());
  api.approvePhase2ValidationBundle.mockResolvedValue(
    bundle({ status: "approved", is_locked: true }),
  );
});

test("shows the gate, progress, deterministic comparison, and sensitivity", async () => {
  render(<Phase2ValidationWorkspace incident={incident} />);

  expect(
    await screen.findByText("phase-2-validation-v1-provisional", {
      selector: "strong",
    }),
  ).toBeInTheDocument();
  expect(
    screen.getByText("Qualified review allowlist enabled"),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("progressbar", {
      name: "Validation progress for bundle-1",
    }),
  ).toHaveAttribute("aria-valuenow", "100");
  expect(screen.getByText(/Within tolerance: 3/)).toBeInTheDocument();
  expect(
    screen.getByText(/Coverage conservative \/ nominal \/ optimistic: 8000/),
  ).toBeInTheDocument();
});

test("queues the selected approved chain and performs explicit approval", async () => {
  const user = userEvent.setup();
  render(<Phase2ValidationWorkspace incident={incident} />);
  await screen.findByText("phase-2-validation-v1-provisional", {
    selector: "strong",
  });

  await user.selectOptions(
    screen.getByLabelText("Approved ICS 205 revision"),
    "revision-1",
  );
  await user.selectOptions(
    screen.getByLabelText("Approved HAAT calculation"),
    "haat-1",
  );
  await user.selectOptions(
    screen.getByLabelText("Approved band/environment estimate"),
    "coverage-1",
  );
  await user.selectOptions(
    screen.getByLabelText("Approved directional estimate"),
    "directional-1",
  );
  await user.selectOptions(
    screen.getByLabelText("Approved incident-local calibration"),
    "calibration-1",
  );
  await user.click(
    screen.getByRole("button", {
      name: "Queue immutable validation evidence",
    }),
  );
  expect(api.createPhase2ValidationBundle).toHaveBeenCalledWith({
    incident: incident.id,
    approved_revision: "revision-1",
    haat_calculation: "haat-1",
    coverage_estimate: "coverage-1",
    directional_analysis: "directional-1",
    calibration_set: "calibration-1",
  });

  const history = screen.getByText("Validation history").parentElement
    ?.parentElement as HTMLElement;
  await user.click(
    within(history).getByRole("button", { name: "Approve evidence" }),
  );
  expect(api.approvePhase2ValidationBundle).toHaveBeenCalledWith("bundle-1");
});

test("announces stale evidence and withholds approval and export controls", async () => {
  api.listPhase2ValidationBundles.mockResolvedValue([
    bundle({
      is_stale: true,
      stale_reasons: ["observation_1_review_changed"],
      approval_eligible: false,
    }),
  ]);
  render(<Phase2ValidationWorkspace incident={incident} />);

  const warning = await screen.findByRole("alert");
  expect(warning).toHaveTextContent("observation_1_review_changed");
  expect(
    screen.getByRole("button", { name: "Approve evidence" }),
  ).toBeDisabled();
  expect(
    screen.queryByRole("button", { name: "Download controlled JSON" }),
  ).not.toBeInTheDocument();
});
