import {
  AUTHENTICATION_EXPIRED_EVENT,
  approveCalibrationSet,
  approveDeconflictionAnalysis,
  approveHAATCalculation,
  approveSubscriberProfileVersion,
  archiveSubscriberProfile,
  copySubscriberProfileVersion,
  createCalibrationSet,
  createDeconflictionAnalysis,
  createFieldObservation,
  createHAATCalculation,
  createRFAnalysisInputSnapshot,
  createSubscriberProfile,
  getElevationProviderStatus,
  getCalibrationStatus,
  getDeconflictionStatus,
  hasActiveSession,
  listCalibrationSets,
  listDeconflictionAnalyses,
  listFieldObservations,
  listHAATCalculations,
  listRFAnalysisInputSnapshots,
  listSubscriberProfiles,
  listSubscriberProfileVersions,
  login,
  logout,
  retryHAATCalculation,
  reviewFieldObservation,
  updateSubscriberProfile,
  updateSubscriberProfileVersion,
} from "../src/api";
import type { EditableRFInputFields } from "../src/types";

beforeEach(() => {
  sessionStorage.clear();
  vi.restoreAllMocks();
});

test("clears a locally expired token and notifies the interface", () => {
  sessionStorage.setItem("ict-toolkit-token", "expired-token");
  sessionStorage.setItem(
    "ict-toolkit-token-expires-at",
    "2000-01-01T00:00:00Z",
  );
  const listener = vi.fn();
  window.addEventListener(AUTHENTICATION_EXPIRED_EVENT, listener, {
    once: true,
  });

  expect(hasActiveSession()).toBe(false);
  expect(listener).toHaveBeenCalledOnce();
  expect(sessionStorage.getItem("ict-toolkit-token")).toBeNull();
});

test("clears the browser session when server logout cannot be confirmed", async () => {
  sessionStorage.setItem("ict-toolkit-token", "network-failure-token");
  sessionStorage.setItem(
    "ict-toolkit-token-expires-at",
    "2099-07-27T20:00:00Z",
  );
  vi.spyOn(globalThis, "fetch").mockRejectedValue(
    new Error("Network unavailable"),
  );

  await expect(logout()).resolves.toBe(false);
  expect(sessionStorage.getItem("ict-toolkit-token")).toBeNull();
  expect(sessionStorage.getItem("ict-toolkit-token-expires-at")).toBeNull();
});

test("rejects a malformed sign-in response without storing credentials", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ token: "unbounded-token" }), { status: 200 }),
  );

  await expect(login("synthetic-user", "synthetic-password")).rejects.toThrow(
    "sign-in response was invalid",
  );
  expect(sessionStorage.getItem("ict-toolkit-token")).toBeNull();
});

test("uses the incident-scoped RF profile and immutable snapshot endpoints", async () => {
  sessionStorage.setItem("ict-toolkit-token", "synthetic-rf-token");
  sessionStorage.setItem(
    "ict-toolkit-token-expires-at",
    "2099-07-27T20:00:00Z",
  );
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input, options) => {
      const url = String(input);
      if (
        options?.method === "POST" &&
        url.endsWith("/api/subscriber-profiles/profile-1/archive/")
      ) {
        return new Response(null, { status: 204 });
      }
      if (
        url.includes("/api/subscriber-profiles/?") ||
        url.includes("/api/subscriber-profile-versions/?") ||
        url.includes("/api/rf-analysis-input-snapshots/?")
      ) {
        return new Response(
          JSON.stringify({
            count: 0,
            next: null,
            previous: null,
            results: [],
          }),
          { status: 200 },
        );
      }
      return new Response(JSON.stringify({ id: "synthetic-result" }), {
        status: 200,
      });
    });

  const initialVersion: EditableRFInputFields = {
    tx_frequency_hz: 155000000,
    rx_frequency_hz: null,
    transmitter_power_w: "5.2500",
    effective_radiated_power_w: null,
    erp_source: "entered",
    receiver_sensitivity_dbm: "-119.50",
    antenna_model: null,
    antenna_gain_db: "2.15",
    antenna_gain_reference: "dbi",
    feed_line_type: null,
    feed_line_length_m: null,
    feed_line_loss_db: null,
    additional_system_loss_db: null,
    polarization: "vertical",
    frequency_band: "vhf_high",
    emission_designator: "11K2F3E",
    emission_bandwidth_hz: 11200,
    mounting_type: "handheld",
    antenna_center_agl_m: "1.50",
    antenna_center_amsl_m: null,
    haat_m: null,
    input_basis: "modeled_assumption",
    notes: "Not operational data",
  };

  await listSubscriberProfiles("incident / one");
  await createSubscriberProfile({
    incident: "incident-1",
    name: "Synthetic Portable",
    profile_type: "portable",
    description: "Synthetic only",
    initial_version: initialVersion,
  });
  await updateSubscriberProfile("profile-1", {
    description: "Revised synthetic description",
  });
  await archiveSubscriberProfile("profile-1");
  await listSubscriberProfileVersions("profile / one");
  await updateSubscriberProfileVersion("version-1", initialVersion);
  await copySubscriberProfileVersion("version-1");
  await approveSubscriberProfileVersion("version-1");
  await createRFAnalysisInputSnapshot("version-1", "Synthetic baseline");
  await listRFAnalysisInputSnapshots("incident / one");

  const calls = fetchMock.mock.calls;
  expect(String(calls[0][0])).toBe(
    "http://localhost:8000/api/subscriber-profiles/?incident=incident%20%2F%20one",
  );
  expect(calls[1][1]).toEqual(
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({
        incident: "incident-1",
        name: "Synthetic Portable",
        profile_type: "portable",
        description: "Synthetic only",
        initial_version: initialVersion,
      }),
    }),
  );
  expect(calls[2][1]).toEqual(
    expect.objectContaining({
      method: "PATCH",
      body: JSON.stringify({
        description: "Revised synthetic description",
      }),
    }),
  );
  expect(String(calls[3][0])).toBe(
    "http://localhost:8000/api/subscriber-profiles/profile-1/archive/",
  );
  expect(String(calls[4][0])).toBe(
    "http://localhost:8000/api/subscriber-profile-versions/?profile=profile%20%2F%20one",
  );
  expect(calls[5][1]).toEqual(
    expect.objectContaining({
      method: "PATCH",
      body: JSON.stringify(initialVersion),
    }),
  );
  expect(String(calls[6][0])).toBe(
    "http://localhost:8000/api/subscriber-profile-versions/version-1/copy/",
  );
  expect(String(calls[7][0])).toBe(
    "http://localhost:8000/api/subscriber-profile-versions/version-1/approve/",
  );
  expect(calls[8][1]).toEqual(
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ label: "Synthetic baseline" }),
    }),
  );
  expect(String(calls[9][0])).toBe(
    "http://localhost:8000/api/rf-analysis-input-snapshots/?incident=incident%20%2F%20one",
  );
  expect(calls[0][1]?.headers).toEqual(
    expect.objectContaining({
      Authorization: "Token synthetic-rf-token",
    }),
  );
});

test("uses source-aware elevation and immutable HAAT workflow endpoints", async () => {
  sessionStorage.setItem("ict-toolkit-token", "synthetic-haat-token");
  sessionStorage.setItem(
    "ict-toolkit-token-expires-at",
    "2099-07-27T20:00:00Z",
  );
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes("/api/haat-calculations/?")) {
        return new Response(
          JSON.stringify({
            count: 0,
            next: null,
            previous: null,
            results: [],
          }),
          { status: 200 },
        );
      }
      return new Response(JSON.stringify({ id: "haat-result" }), {
        status: 200,
      });
    });

  await getElevationProviderStatus();
  await listHAATCalculations("incident / one");
  await createHAATCalculation({
    site: "site-1",
    rf_input_snapshot: "rf-snapshot-1",
    radial_count: 8,
    start_azimuth_deg: "0.000",
    sampling_interval_m: 1000,
    inner_distance_m: 3000,
    outer_distance_m: 16000,
    rounding_m: "0.100",
    force_refresh: false,
  });
  await retryHAATCalculation("haat-1");
  await approveHAATCalculation("haat-1");

  expect(String(fetchMock.mock.calls[0][0])).toBe(
    "http://localhost:8000/api/elevation-provider/",
  );
  expect(String(fetchMock.mock.calls[1][0])).toBe(
    "http://localhost:8000/api/haat-calculations/?incident=incident%20%2F%20one",
  );
  expect(fetchMock.mock.calls[2][1]).toEqual(
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({
        site: "site-1",
        rf_input_snapshot: "rf-snapshot-1",
        radial_count: 8,
        start_azimuth_deg: "0.000",
        sampling_interval_m: 1000,
        inner_distance_m: 3000,
        outer_distance_m: 16000,
        rounding_m: "0.100",
        force_refresh: false,
      }),
    }),
  );
  expect(String(fetchMock.mock.calls[3][0])).toBe(
    "http://localhost:8000/api/haat-calculations/haat-1/retry/",
  );
  expect(String(fetchMock.mock.calls[4][0])).toBe(
    "http://localhost:8000/api/haat-calculations/haat-1/approve/",
  );
});

test("uses incident-scoped field observation and calibration endpoints", async () => {
  sessionStorage.setItem("ict-toolkit-token", "synthetic-calibration-token");
  sessionStorage.setItem(
    "ict-toolkit-token-expires-at",
    "2099-07-28T20:00:00Z",
  );
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input) => {
      const url = String(input);
      if (
        url.includes("/api/field-observations/?") ||
        url.includes("/api/calibration-sets/?")
      ) {
        return new Response(
          JSON.stringify({
            count: 0,
            next: null,
            previous: null,
            results: [],
          }),
          { status: 200 },
        );
      }
      return new Response(JSON.stringify({ id: "synthetic-result" }), {
        status: 200,
      });
    });

  await getCalibrationStatus();
  await listFieldObservations("incident / calibration");
  await createFieldObservation({
    incident: "incident-1",
    infrastructure_rf_input_snapshot: "rf-infrastructure",
    subscriber_rf_input_snapshot: "rf-subscriber",
    classification: "good",
    evidence_type: "measured",
    observed_from: "2026-07-28T14:00:00Z",
    observed_to: "2026-07-28T14:05:00Z",
    location_precision: "redacted",
    latitude: null,
    longitude: null,
    location_precision_m: null,
    observer_source: "Synthetic team",
    collection_method: "Scripted check",
    environment: {},
    measurements: {
      measured_distance_m: "1000",
      predicted_distance_m: "900",
    },
    notes: "Synthetic only",
    quality_flags: [],
    source_record_id: "",
    source_revision: "synthetic-v1",
  });
  await reviewFieldObservation(
    "observation-1",
    "approved",
    "Synthetic review reason",
  );
  await listCalibrationSets("incident / calibration");
  await createCalibrationSet({
    incident: "incident-1",
    name: "Synthetic local calibration",
    observations: ["observation-1"],
    baseline_preset: "balanced",
    baseline_preset_version: "balanced-v1-provisional",
    parameters: {
      minimum_samples: 3,
      minimum_ratio: "0.25",
      maximum_ratio: "4",
    },
  });
  await approveCalibrationSet("calibration-1");

  expect(String(fetchMock.mock.calls[0][0])).toBe(
    "http://localhost:8000/api/calibration-status/",
  );
  expect(String(fetchMock.mock.calls[1][0])).toBe(
    "http://localhost:8000/api/field-observations/?incident=incident%20%2F%20calibration",
  );
  expect(fetchMock.mock.calls[2][1]).toEqual(
    expect.objectContaining({
      method: "POST",
      body: expect.stringContaining('"location_precision":"redacted"'),
    }),
  );
  expect(fetchMock.mock.calls[3][1]).toEqual(
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({
        decision: "approved",
        reason: "Synthetic review reason",
      }),
    }),
  );
  expect(String(fetchMock.mock.calls[4][0])).toBe(
    "http://localhost:8000/api/calibration-sets/?incident=incident%20%2F%20calibration",
  );
  expect(fetchMock.mock.calls[5][1]).toEqual(
    expect.objectContaining({
      method: "POST",
      body: expect.stringContaining('"observations":["observation-1"]'),
    }),
  );
  expect(String(fetchMock.mock.calls[6][0])).toBe(
    "http://localhost:8000/api/calibration-sets/calibration-1/approve/",
  );
});

test("uses the versioned deconfliction status, analysis, and approval endpoints", async () => {
  sessionStorage.setItem("ict-toolkit-token", "synthetic-deconfliction-token");
  sessionStorage.setItem(
    "ict-toolkit-token-expires-at",
    "2099-07-28T20:00:00Z",
  );
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes("/api/deconfliction-analyses/?")) {
        return new Response(
          JSON.stringify({
            count: 0,
            next: null,
            previous: null,
            results: [],
          }),
          { status: 200 },
        );
      }
      return new Response(JSON.stringify({ id: "deconfliction-result" }), {
        status: 200,
      });
    });

  await getDeconflictionStatus();
  await listDeconflictionAnalyses("incident / deconfliction");
  await createDeconflictionAnalysis({
    incident: "incident-1",
    approved_revision: "revision-1",
    active_resources: ["resource-1"],
  });
  await approveDeconflictionAnalysis("analysis-1");

  expect(String(fetchMock.mock.calls[0][0])).toBe(
    "http://localhost:8000/api/deconfliction-status/",
  );
  expect(String(fetchMock.mock.calls[1][0])).toBe(
    "http://localhost:8000/api/deconfliction-analyses/?incident=incident%20%2F%20deconfliction",
  );
  expect(fetchMock.mock.calls[2][1]).toEqual(
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({
        incident: "incident-1",
        approved_revision: "revision-1",
        active_resources: ["resource-1"],
      }),
    }),
  );
  expect(String(fetchMock.mock.calls[3][0])).toBe(
    "http://localhost:8000/api/deconfliction-analyses/analysis-1/approve/",
  );
});
