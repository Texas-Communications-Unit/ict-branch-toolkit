import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { TerrainAnalysisWorkspace } from "../src/TerrainAnalysisWorkspace";
import type {
  CoverageEstimate,
  Incident,
  TerrainAnalysis,
  TerrainAnalysisStatus,
} from "../src/types";

const api = vi.hoisted(() => ({
  approveTerrainAnalysis: vi.fn(),
  cancelTerrainAnalysis: vi.fn(),
  createTerrainAnalysis: vi.fn(),
  getTerrainAnalysisStatus: vi.fn(),
  listCoverageEstimates: vi.fn(),
  listTerrainAnalyses: vi.fn(),
  retryTerrainAnalysis: vi.fn(),
  runTerrainAnalysis: vi.fn(),
}));

vi.mock("../src/api", () => api);

const incident: Incident = {
  id: "incident-terrain-1",
  name: "Synthetic terrain exercise",
  incident_number: "SYN-TERRAIN",
  status: "planning",
  operational_periods: [],
  archived_at: null,
  permissions: ["rf.view", "rf.edit", "rf.approve"],
};

const capability: TerrainAnalysisStatus = {
  provider: {
    provider: "synthetic-offline",
    provider_version: "terrain-profile-provider-v1",
    dataset_product: "ICT Toolkit deterministic terrain profile fixture",
    dataset_version: "synthetic-terrain-profile-v1",
    horizontal_crs: "EPSG:4326",
    vertical_crs: "SYNTHETIC:LOCAL-OFFSET",
    target_vertical_crs: "SYNTHETIC:LOCAL",
    resolution_m: "30.000",
    license_terms_url: "https://example.invalid/synthetic-terrain",
    permitted_use: "Synthetic fixtures only.",
    coverage: { type: "synthetic" },
    source_content_sha256: "a".repeat(64),
    offline: true,
  },
  provider_configuration: { synthetic_mode: "ridge" },
  engine: {
    engine: "provisional_sampled_line_of_sight",
    engine_version: "sampled-line-of-sight-v1-provisional",
    method: "sampled cumulative line-of-sight screening",
    approved_for_operational_use: false,
    capabilities: {
      terrain_profile: true,
      sampled_line_of_sight: true,
      diffraction: false,
      clutter: false,
      external_network_required: false,
    },
    parameters: {
      effective_earth_radius_factor: "1.333333333",
      material_difference_percent: "10",
      material_difference_minimum_m: 1000,
    },
    tested_limits: {
      maximum_distance_m: 200000,
      maximum_samples: 1001,
      interpretation: "Resource bounds, not operational validation.",
    },
    disclaimer: "Planning estimate only.",
  },
  configured: true,
  approved_for_analysis: true,
  available: true,
  execution_model: "explicit synchronous staged job",
  cancellation_boundary: "Queued work can be cancelled before execution.",
  resource_safety_limits: {
    maximum_distance_m: 200000,
    maximum_samples: 1001,
  },
  warning: "",
  classification: "NON-PRODUCTION P3.1 TERRAIN DECISION SUPPORT",
  disclaimer: "Planning estimate only.",
};

const coverage = {
  id: "coverage-1",
  incident: incident.id,
  site_name: "Synthetic ridge site",
  status: "approved",
  calculation_state: "complete",
  environment: "rural",
  nominal_distance_m: 10000,
} as CoverageEstimate;

function terrain(overrides: Partial<TerrainAnalysis> = {}): TerrainAnalysis {
  return {
    id: "terrain-1",
    incident: incident.id,
    site: "site-1",
    coverage_estimate: coverage.id,
    supersedes: null,
    provider: capability.provider.provider,
    provider_version: capability.provider.provider_version,
    dataset_product: capability.provider.dataset_product,
    dataset_version: capability.provider.dataset_version,
    engine: capability.engine.engine,
    engine_version: capability.engine.engine_version,
    app_version: "0.2.0-rc.1",
    azimuth_deg: "45.000",
    maximum_distance_m: 10000,
    sample_interval_m: 100,
    receiver_height_m: "1.500",
    clearance_m: "0.000",
    job_state: "complete",
    analysis_state: "partial",
    progress_step: "complete",
    progress_percent: 100,
    status: "draft",
    input_snapshot: {},
    input_sha256: "b".repeat(64),
    result_snapshot: {
      profile: {
        acquisition_state: "partial",
        requested_distance_m: 10000,
        sample_interval_m: 100,
        sample_count: 4,
        complete_sample_count: 3,
        gap_count: 1,
        edge_effect: true,
        sample_sha256: "c".repeat(64),
        samples: [
          {
            distance_m: 0,
            azimuth_deg: "45.000",
            latitude: "33.000000",
            longitude: "-97.000000",
            state: "complete",
            source_elevation_m: "100.000",
            terrain_elevation_m: "100.000",
            reason: "",
            visible: true,
          },
          {
            distance_m: 100,
            azimuth_deg: "45.000",
            latitude: "33.000100",
            longitude: "-96.999900",
            state: "complete",
            source_elevation_m: "220.000",
            terrain_elevation_m: "220.000",
            reason: "",
            visible: false,
          },
          {
            distance_m: 200,
            azimuth_deg: "45.000",
            latitude: "33.000200",
            longitude: "-96.999800",
            state: "missing",
            source_elevation_m: null,
            terrain_elevation_m: null,
            reason: "Synthetic missing tile.",
            visible: null,
          },
          {
            distance_m: 300,
            azimuth_deg: "45.000",
            latitude: "33.000300",
            longitude: "-96.999700",
            state: "out_of_coverage",
            source_elevation_m: null,
            terrain_elevation_m: null,
            reason: "Synthetic coverage edge.",
            visible: null,
          },
        ],
      },
      line_of_sight: {
        continuous_clear_distance_m: 0,
        first_obstruction_or_gap_distance_m: 100,
        obstruction_count: 1,
        receiver_height_m: "1.500",
        clearance_m: "0.000",
        effective_earth_radius_factor: "1.333333333",
      },
      comparison: {
        phase2_nominal_distance_m: 10000,
        terrain_continuous_los_distance_m: 0,
        difference_m: -10000,
        difference_percent: "-100.000",
        material_threshold_m: 1000,
        materially_different: true,
        interpretation:
          "The terrain result is materially shorter than the Phase 2 estimate.",
        layer_behavior:
          "Terrain evidence is separate and never replaces the Phase 2 estimate.",
      },
      warnings: [
        "Synthetic terrain only.",
        "Profile gaps are not interpolated.",
      ],
      explanation: "Synthetic ridge comparison for deterministic tests.",
    },
    result_sha256: "d".repeat(64),
    failure_code: "",
    failure_message: "",
    created_by: 1,
    approved_by: null,
    created_at: "2026-07-28T12:00:00Z",
    started_at: "2026-07-28T12:01:00Z",
    completed_at: "2026-07-28T12:02:00Z",
    approved_at: null,
    updated_at: "2026-07-28T12:02:00Z",
    is_locked: false,
    is_stale: false,
    stale_reasons: [],
    approval_eligible: false,
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  api.getTerrainAnalysisStatus.mockResolvedValue(capability);
  api.listCoverageEstimates.mockResolvedValue([coverage]);
  api.listTerrainAnalyses.mockResolvedValue({
    count: 1,
    next: null,
    previous: null,
    results: [terrain()],
  });
  api.createTerrainAnalysis.mockResolvedValue(
    terrain({
      id: "terrain-queued",
      job_state: "queued",
      analysis_state: "",
      progress_percent: 0,
    }),
  );
  api.runTerrainAnalysis.mockResolvedValue(terrain());
});

test("shows capability, separate comparison, and text-distinct profile states", async () => {
  const user = userEvent.setup();
  render(<TerrainAnalysisWorkspace incident={incident} />);

  expect(
    (
      await screen.findAllByText(
        /ICT Toolkit deterministic terrain profile fixture/,
      )
    ).length,
  ).toBeGreaterThan(0);
  expect(screen.getByText(/sampled line of sight: yes/)).toBeInTheDocument();
  expect(screen.getByText("Phase 2 nominal estimate")).toBeInTheDocument();
  expect(screen.getByText("Terrain continuous clear path")).toBeInTheDocument();
  expect(screen.getByText(/Material difference detected/)).toBeInTheDocument();

  await user.click(screen.getByText("Accessible terrain profile (4 samples)"));
  const table = screen.getByRole("table");
  expect(within(table).getByText("obstructed")).toBeInTheDocument();
  expect(within(table).getByText("missing")).toBeInTheDocument();
  expect(within(table).getByText("out of coverage")).toBeInTheDocument();
});

test("queues bounded inputs and runs only after an explicit action", async () => {
  api.listTerrainAnalyses.mockResolvedValue({
    count: 1,
    next: null,
    previous: null,
    results: [
      terrain({
        job_state: "queued",
        analysis_state: "",
        progress_percent: 0,
        result_snapshot: {},
        result_sha256: "",
      }),
    ],
  });
  const user = userEvent.setup();
  render(<TerrainAnalysisWorkspace incident={incident} />);
  await screen.findAllByText(
    /ICT Toolkit deterministic terrain profile fixture/,
  );

  await user.selectOptions(
    screen.getByLabelText("Approved Phase 2 coverage estimate"),
    coverage.id,
  );
  await user.clear(screen.getByLabelText("Azimuth (degrees)"));
  await user.type(screen.getByLabelText("Azimuth (degrees)"), "90");
  await user.click(
    screen.getByRole("button", { name: "Queue terrain profile" }),
  );

  expect(api.createTerrainAnalysis).toHaveBeenCalledWith({
    coverage_estimate: coverage.id,
    azimuth_deg: "90",
    maximum_distance_m: 10000,
    sample_interval_m: 100,
    receiver_height_m: "1.5",
    clearance_m: "0",
  });

  await user.click(
    screen.getByRole("button", { name: "Run terrain analysis" }),
  );
  expect(api.runTerrainAnalysis).toHaveBeenCalledWith("terrain-1");
});

test("fails closed and withholds approval for partial or stale evidence", async () => {
  api.getTerrainAnalysisStatus.mockResolvedValue({
    ...capability,
    approved_for_analysis: false,
    available: false,
    warning: "The exact terrain configuration is not allowlisted.",
  });
  api.listTerrainAnalyses.mockResolvedValue({
    count: 1,
    next: null,
    previous: null,
    results: [
      terrain({
        is_stale: true,
        stale_reasons: ["terrain_configuration_changed"],
        approval_eligible: false,
      }),
    ],
  });
  render(<TerrainAnalysisWorkspace incident={incident} />);

  expect(await screen.findByText("fail closed")).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "Queue terrain profile" }),
  ).toBeDisabled();
  expect(
    screen.getByRole("button", { name: "Approve terrain evidence" }),
  ).toBeDisabled();
  expect(screen.getByText(/terrain_configuration_changed/)).toHaveTextContent(
    "terrain_configuration_changed",
  );
});

test("pages retained terrain history without rendering every profile up front", async () => {
  api.listTerrainAnalyses
    .mockResolvedValueOnce({
      count: 6,
      next: "http://test.invalid/api/terrain-analyses/?page=2",
      previous: null,
      results: [terrain()],
    })
    .mockResolvedValueOnce({
      count: 6,
      next: null,
      previous: "http://test.invalid/api/terrain-analyses/?page=1",
      results: [terrain({ id: "terrain-6", azimuth_deg: "180.000" })],
    });
  const user = userEvent.setup();
  render(<TerrainAnalysisWorkspace incident={incident} />);

  expect(await screen.findByText("Page 1 · 6 retained")).toBeInTheDocument();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Next terrain page" }));
  expect(await screen.findByText("Page 2 · 6 retained")).toBeInTheDocument();
  expect(api.listTerrainAnalyses).toHaveBeenLastCalledWith(incident.id, 2);
  expect(
    screen.getByRole("button", { name: "Previous terrain page" }),
  ).toBeEnabled();
});
