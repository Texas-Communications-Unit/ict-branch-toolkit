import { expect, test } from "@playwright/test";

import {
  expectDocumentReflow,
  expectNoAccessibilityViolations,
} from "./accessibility";

test("administrator signs in and sees the incident planning workspace", async ({
  page,
}, testInfo) => {
  let approved = false;
  let rfProfileCreated = false;
  let rfApproved = false;
  let haatCreated = false;
  let haatApproved = false;
  let fieldObservationCreated = false;
  let fieldObservationApproved = false;
  let calibrationCreated = false;
  let rfInputs = {
    tx_frequency_hz: null as number | null,
    rx_frequency_hz: null as number | null,
    transmitter_power_w: null as string | null,
    effective_radiated_power_w: null as string | null,
    erp_source: "unknown",
    receiver_sensitivity_dbm: null as string | null,
    antenna_model: null as string | null,
    antenna_gain_db: null as string | null,
    antenna_gain_reference: "unknown",
    feed_line_type: null as string | null,
    feed_line_length_m: null as string | null,
    feed_line_loss_db: null as string | null,
    additional_system_loss_db: null as string | null,
    polarization: "unknown",
    frequency_band: "unknown",
    emission_designator: null as string | null,
    emission_bandwidth_hz: null as number | null,
    mounting_type: "unknown",
    antenna_center_agl_m: null as string | null,
    antenna_center_amsl_m: null as string | null,
    haat_m: null as string | null,
    input_basis: "unknown",
    notes: null as string | null,
  };
  const rfProfile = {
    id: "rf-profile-1",
    incident: "syn-1",
    name: "Synthetic Portable Assumption",
    profile_type: "portable",
    description: "Synthetic exercise values only",
    archived_at: null,
  };
  const rfVersion = () => ({
    id: "rf-version-1",
    profile: "rf-profile-1",
    number: 1,
    status: rfApproved ? "approved" : "draft",
    is_locked: rfApproved,
    approved_at: rfApproved ? "2026-07-27T22:00:00Z" : null,
    ...rfInputs,
    erp_calculation_path: rfApproved
      ? {
          formula: "transmitter_power_w + antenna_gain_db - system_losses_db",
          synthetic: true,
        }
      : null,
    input_snapshot: null,
    input_sha256: null,
  });
  const rfInputSnapshot = () => ({
    id: "rf-snapshot-1",
    incident: "syn-1",
    profile_version: "rf-version-1",
    profile_name: "Synthetic Portable Assumption",
    profile_type: "portable",
    profile_version_number: 1,
    label: "Synthetic RF baseline",
    input_snapshot: {
      schema_version: 1,
      profile: {
        id: "rf-profile-1",
        incident: "syn-1",
        name: "Synthetic Portable Assumption",
        profile_type: "portable",
      },
      profile_version: { id: "rf-version-1", number: 1 },
      inputs: { ...rfInputs },
    },
    input_sha256: "b".repeat(64),
    archived_at: null,
    created_at: "2026-07-27T22:05:00Z",
  });
  const subscriberRFInputSnapshot = () => ({
    ...rfInputSnapshot(),
    id: "rf-snapshot-2",
    label: "Synthetic subscriber baseline",
    profile_name: "Synthetic portable subscriber",
    input_sha256: "a".repeat(64),
    input_snapshot: {
      ...rfInputSnapshot().input_snapshot,
      profile: {
        id: "rf-profile-2",
        incident: "syn-1",
        name: "Synthetic portable subscriber",
        profile_type: "portable",
      },
      profile_version: { id: "rf-version-2", number: 1 },
    },
  });
  const fieldObservation = () => ({
    id: "observation-1",
    incident: "syn-1",
    infrastructure_rf_input_snapshot: "rf-snapshot-1",
    infrastructure_label: "Synthetic RF baseline",
    subscriber_rf_input_snapshot: "rf-snapshot-2",
    subscriber_label: "Synthetic subscriber baseline",
    coverage_estimate: null,
    directional_analysis: null,
    supersedes: null,
    superseded_by: null,
    classification: "good",
    evidence_type: "measured",
    observed_from: "2026-07-28T14:00:00Z",
    observed_to: "2026-07-28T14:05:00Z",
    location_precision: "redacted",
    coordinate_reference: "EPSG:4326",
    latitude: null,
    longitude: null,
    location_precision_m: null,
    direction_degrees: null,
    path_distance_m: null,
    observer_source: "Synthetic exercise team",
    collection_method: "Scripted field check",
    environment: {},
    measurements: {
      measured_distance_m: "1000",
      predicted_distance_m: "900",
    },
    notes: "",
    quality_flags: [],
    source_record_id: "",
    source_revision: "synthetic-observation-v1",
    input_snapshot: {},
    input_sha256: "8".repeat(64),
    created_by: 1,
    created_at: "2026-07-28T14:06:00Z",
    current_review_state: fieldObservationApproved ? "approved" : "pending",
    reviews: fieldObservationApproved
      ? [
          {
            id: "review-1",
            observation: "observation-1",
            decision: "approved",
            reason: "Synthetic review reason",
            evidence_sha256: "7".repeat(64),
            reviewed_by: 1,
            reviewed_at: "2026-07-28T14:10:00Z",
          },
        ]
      : [],
  });
  const calibrationSet = () => ({
    id: "calibration-set-1",
    incident: "syn-1",
    name: "Incident-local field calibration",
    version: 1,
    status: "draft",
    calculation_state: "complete",
    algorithm: "observation-envelope",
    algorithm_version: "observation-envelope-v1-provisional",
    parameters: {
      minimum_samples: 3,
      minimum_ratio: "0.25",
      maximum_ratio: "4",
    },
    baseline_preset: "balanced",
    baseline_preset_version: "balanced-v1-provisional",
    observation_ids: ["observation-1"],
    observation_snapshot: [],
    observation_sha256: "6".repeat(64),
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
    warnings: ["Synthetic fixture only."],
    exclusions: [],
    result_snapshot: {},
    result_sha256: "5".repeat(64),
    approved_at: null,
    created_at: "2026-07-28T15:00:00Z",
    is_locked: false,
  });
  const haatCalculation = () => ({
    id: "haat-1",
    incident: "syn-1",
    site: "site-1",
    site_name: "Synthetic Command Site",
    profile_version: "rf-version-1",
    profile_name: "Synthetic Portable Assumption",
    profile_version_number: 1,
    rf_input_snapshot: "rf-snapshot-1",
    rf_input_label: "Synthetic RF baseline",
    elevation_snapshot: "elevation-1",
    elevation: {
      id: "elevation-1",
      incident: "syn-1",
      site: "site-1",
      query_sha256: "c".repeat(64),
      provider: "synthetic-offline",
      dataset_product: "ICT Toolkit deterministic terrain fixture (flat)",
      horizontal_crs: "EPSG:4326",
      vertical_crs: "SYNTHETIC:LOCAL",
      target_vertical_crs: "SYNTHETIC:LOCAL",
      resolution_m: "30.000",
      source_version: "synthetic-terrain-v1",
      source_retrieved_at: "2026-07-27T22:10:00Z",
      license_terms_url: "",
      permitted_use: "Synthetic fixture data only.",
      coverage: { type: "synthetic" },
      source_content_sha256: "d".repeat(64),
      acquisition_state: "complete",
      current_state: "complete",
      sample_sha256: "e".repeat(64),
      transformation: { method: "identity" },
      warnings: ["Synthetic fixture only."],
      retrieved_at: "2026-07-27T22:10:00Z",
      stale_at: "2026-08-03T22:10:00Z",
    },
    supersedes: null,
    status: haatApproved ? "approved" : "draft",
    calculation_state: "complete",
    method: "general_radial_average_terrain",
    method_version: "haat-radial-average-v1-provisional",
    radial_count: 8,
    start_azimuth_deg: "0.000",
    sampling_interval_m: 1000,
    inner_distance_m: 3000,
    outer_distance_m: 16000,
    rounding_m: "0.100",
    antenna_agl_m: "12.500",
    site_elevation_m: "100.000",
    antenna_amsl_m: "112.500",
    average_terrain_m: "100.000",
    haat_m: "12.500",
    sample_count: 112,
    excluded_sample_count: 0,
    algorithm_snapshot: {
      method_scope: "General planning radial-average terrain method.",
    },
    exclusions: [],
    warnings: ["Synthetic fixture only."],
    result_snapshot: {},
    result_sha256: "f".repeat(64),
    approved_at: haatApproved ? "2026-07-27T22:15:00Z" : null,
    created_at: "2026-07-27T22:10:00Z",
    is_locked: haatApproved,
  });
  await page.route("**/api/auth/token/", (route) =>
    route.fulfill({
      json: {
        token: "synthetic-token",
        expires_at: "2099-07-27T20:00:00Z",
      },
    }),
  );
  await page.route("**/api/incidents/", (route) =>
    route.fulfill({
      json: {
        count: 1,
        next: null,
        previous: null,
        results: [
          {
            id: "syn-1",
            name: "Synthetic Flood Exercise",
            incident_number: "SYN-001",
            status: "planning",
            operational_periods: [
              {
                id: "period-1",
                name: "Operational Period 1",
                starts_at: "2026-07-23T08:00:00Z",
                ends_at: "2026-07-23T20:00:00Z",
              },
            ],
            archived_at: null,
            permissions: [
              "incident.view",
              "incident.archive",
              "period.create",
              "plan.view",
              "plan.edit",
              "plan.approve",
              "plan.export",
              "site.view",
              "site.edit",
              "site.export",
              "rf.view",
              "rf.edit",
              "rf.approve",
            ],
          },
        ],
      },
    }),
  );
  await page.route("**/api/me/", (route) =>
    route.fulfill({
      json: {
        username: "admin",
        display_name: "Synthetic Administrator",
        role: "administrator",
        permissions: ["incident.create", "library.import"],
      },
    }),
  );
  await page.route("**/api/conventional-channels/", (route) =>
    route.fulfill({
      json: { count: 0, next: null, previous: null, results: [] },
    }),
  );
  await page.route("**/api/trunked-talkgroups/", (route) =>
    route.fulfill({
      json: { count: 0, next: null, previous: null, results: [] },
    }),
  );
  await page.route("**/api/ics205-plans/", (route) =>
    route.fulfill({
      json: {
        count: 1,
        next: null,
        previous: null,
        results: [
          {
            id: "plan-1",
            incident: "syn-1",
            operational_period: "period-1",
            title: "Incident Radio Communications Plan",
            revisions: [
              {
                id: "rev-1",
                plan: "plan-1",
                number: 1,
                status: approved ? "approved" : "draft",
                is_locked: approved,
                prepared_by_name: "Synthetic Planner",
                prepared_by_position: "COML",
                approved_at: approved ? "2026-07-23T20:00:00Z" : null,
                relationships: [],
                assignments: [
                  {
                    id: "row-1",
                    revision: "rev-1",
                    position: 1,
                    function: "Command",
                    channel_name: "SYN CALL",
                    assignment: "Incident command",
                    rx_frequency_hz: 155001000,
                    tx_frequency_hz: 155001000,
                    rx_squelch: "CSQ",
                    tx_squelch: "CSQ",
                    mode: "Analog FM",
                    remarks: "Synthetic only",
                    structured_note: "",
                    contact_name: "",
                    site_address: "",
                    phone_numbers: "",
                    contact_24_hour: "",
                    resource_snapshot: { type: "incident" },
                  },
                ],
              },
            ],
          },
        ],
      },
    }),
  );
  await page.route("**/api/radio-sites/?*", (route) =>
    route.fulfill({
      json: {
        count: 1,
        next: null,
        previous: null,
        results: [
          {
            id: "site-1",
            incident: "syn-1",
            name: "Synthetic Command Site",
            description: "Synthetic fixture",
            latitude: "33.214500",
            longitude: "-97.133100",
            entered_coordinate: "33.214500, -97.133100",
            coordinate_format: "decimal",
            coordinate_formats: {
              decimal: "33.214500, -97.133100",
              ddm: "33° 12.8700′ N, 97° 07.9860′ W",
              dms: "33° 12′ 52.20″ N, 97° 07′ 59.16″ W",
              mgrs: "14SQB7401876781",
            },
            address: "",
            source_identity: "",
            source_retrieved_at: null,
            rings: [
              {
                id: "ring-1",
                site: "site-1",
                ring_type: "operational",
                radius_m: 8000,
                label: "Synthetic operational ring",
              },
            ],
          },
        ],
      },
    }),
  );
  await page.route("**/api/site-assignments/?*", (route) =>
    route.fulfill({
      json: {
        count: 1,
        next: null,
        previous: null,
        results: [
          {
            id: "link-1",
            site: "site-1",
            site_name: "Synthetic Command Site",
            assignment: "row-1",
            assignment_label: "1. Command — SYN CALL",
            site_snapshot: {},
          },
        ],
      },
    }),
  );
  await page.route("**/api/coordinates/parse/", (route) =>
    route.fulfill({
      json: {
        latitude: 33.2145,
        longitude: -97.1331,
        input_format: "dms",
        formats: {
          decimal: "33.214500, -97.133100",
          ddm: "33° 12.8700′ N, 97° 07.9860′ W",
          dms: "33° 12′ 52.20″ N, 97° 07′ 59.16″ W",
          mgrs: "14SQB7401876781",
        },
      },
    }),
  );
  await page.route("**/api/plan-revisions/rev-1/approve/", (route) => {
    approved = true;
    return route.fulfill({ json: {} });
  });
  await page.route("**/api/subscriber-profiles/?incident=*", (route) =>
    route.fulfill({
      json: {
        count: rfProfileCreated ? 1 : 0,
        next: null,
        previous: null,
        results: rfProfileCreated ? [rfProfile] : [],
      },
    }),
  );
  await page.route("**/api/subscriber-profiles/", async (route) => {
    expect(route.request().method()).toBe("POST");
    const payload = route.request().postDataJSON();
    expect(payload).toMatchObject({
      incident: "syn-1",
      name: "Synthetic Portable Assumption",
      profile_type: "portable",
      description: "Synthetic exercise values only",
    });
    expect(payload.initial_version.tx_frequency_hz).toBeNull();
    expect(payload.initial_version.erp_source).toBe("unknown");
    expect(payload.initial_version).not.toHaveProperty("erp_calculation_path");
    rfProfileCreated = true;
    return route.fulfill({ json: rfProfile });
  });
  await page.route("**/api/subscriber-profile-versions/?profile=*", (route) =>
    route.fulfill({
      json: {
        count: rfProfileCreated ? 1 : 0,
        next: null,
        previous: null,
        results: rfProfileCreated ? [rfVersion()] : [],
      },
    }),
  );
  await page.route(
    "**/api/subscriber-profile-versions/rf-version-1/",
    async (route) => {
      expect(route.request().method()).toBe("PATCH");
      rfInputs = route.request().postDataJSON();
      return route.fulfill({ json: rfVersion() });
    },
  );
  await page.route(
    "**/api/subscriber-profile-versions/rf-version-1/approve/",
    (route) => {
      rfApproved = true;
      return route.fulfill({ json: rfVersion() });
    },
  );
  await page.route(
    "**/api/subscriber-profile-versions/rf-version-1/create_snapshot/",
    async (route) => {
      expect(route.request().postDataJSON()).toEqual({
        label: "Synthetic RF baseline",
      });
      return route.fulfill({
        json: rfInputSnapshot(),
      });
    },
  );
  await page.route("**/api/rf-analysis-input-snapshots/?incident=*", (route) =>
    route.fulfill({
      json: {
        count: 2,
        next: null,
        previous: null,
        results: [rfInputSnapshot(), subscriberRFInputSnapshot()],
      },
    }),
  );
  await page.route("**/api/elevation-provider/", (route) =>
    route.fulfill({
      json: {
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
        source_content_sha256: "d".repeat(64),
        offline: true,
        configured: true,
        approved: true,
        available: true,
        warning: "",
      },
    }),
  );
  await page.route("**/api/haat-calculations/?incident=*", (route) =>
    route.fulfill({
      json: {
        count: haatCreated ? 1 : 0,
        next: null,
        previous: null,
        results: haatCreated ? [haatCalculation()] : [],
      },
    }),
  );
  await page.route("**/api/haat-calculations/", async (route) => {
    expect(route.request().method()).toBe("POST");
    expect(route.request().postDataJSON()).toMatchObject({
      site: "site-1",
      rf_input_snapshot: "rf-snapshot-1",
      radial_count: 8,
      start_azimuth_deg: "0",
      sampling_interval_m: 1000,
      inner_distance_m: 3000,
      outer_distance_m: 16000,
      rounding_m: "0.1",
      force_refresh: false,
    });
    haatCreated = true;
    return route.fulfill({ json: haatCalculation() });
  });
  await page.route("**/api/haat-calculations/haat-1/retry/", (route) =>
    route.fulfill({ json: haatCalculation() }),
  );
  await page.route("**/api/haat-calculations/haat-1/approve/", (route) => {
    haatApproved = true;
    return route.fulfill({ json: haatCalculation() });
  });
  await page.route("**/api/coverage-engine/", (route) =>
    route.fulfill({
      json: {
        engine: "provisional_fspl_horizon",
        engine_version: "fspl-horizon-v1-provisional",
        approved_for_operational_use: false,
        approved_presets: [],
        disclaimer:
          "Provisional planning estimate only—not a propagation study, frequency-coordination decision, spectrum authorization, or coverage guarantee.",
        supported_band_groups: [
          {
            name: "vhf_high",
            lower_hz: 136000000,
            upper_hz: 174000000,
          },
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
            maximum_distance_m: 100000,
            distance_rounding_m: 100,
          },
        },
      },
    }),
  );
  await page.route("**/api/coverage-estimates/?incident=*", (route) =>
    route.fulfill({
      json: { count: 0, next: null, previous: null, results: [] },
    }),
  );
  await page.route("**/api/directional-analysis-status/", (route) =>
    route.fulfill({
      json: {
        rule_version: "concentric-minimum-v1-provisional",
        approved_for_operational_use: false,
        rule: "Probable two-way distance is the smaller supported nominal path.",
        disclaimer:
          "Provisional planning estimate only—not a propagation study, frequency-coordination decision, spectrum authorization, or coverage guarantee.",
        supported_profile_types: [
          "portable",
          "mobile",
          "fixed",
          "cache",
          "gateway",
          "configurable",
        ],
      },
    }),
  );
  await page.route(
    "**/api/directional-coverage-analyses/?incident=*",
    (route) =>
      route.fulfill({
        json: { count: 0, next: null, previous: null, results: [] },
      }),
  );
  await page.route("**/api/deconfliction-status/", (route) =>
    route.fulfill({
      json: {
        rule_set_id: "rf-deconfliction",
        rule_set_version: "rf-deconfliction-v2-reviewed",
        approved_for_operational_use: false,
        close_frequency_threshold_hz: 12500,
        rules: [
          {
            id: "RF-001",
            name: "Co-channel overlap",
            severity: "critical",
            summary: "Operating frequencies match and approved areas overlap.",
          },
        ],
        analysis_statuses: [],
        access_code_source_hierarchy: [
          "selected_versioned_channel_definition",
          "approved_subscriber_programming_profile",
        ],
        squelch_rule:
          "CTCSS, DCS, NAC, or equivalent access-code differences never suppress RF-001 or RF-002.",
        disclaimer:
          "Decision support only. Results do not constitute frequency coordination, spectrum authorization, an interference determination, a propagation study, or operational approval. Qualified practitioners must review the results before operational use.",
      },
    }),
  );
  await page.route("**/api/deconfliction-analyses/?incident=*", (route) =>
    route.fulfill({
      json: { count: 0, next: null, previous: null, results: [] },
    }),
  );
  await page.route("**/api/calibration-status/", (route) =>
    route.fulfill({
      json: {
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
      },
    }),
  );
  await page.route("**/api/phase2-validation-status/", (route) =>
    route.fulfill({
      json: {
        validation_profile_id: "phase-2-validation",
        validation_profile_version: "phase-2-validation-v1-provisional",
        validation_method_version:
          "deterministic-distance-ratio-comparison-v1-provisional",
        approved_for_release_candidate_use: false,
        execution_model: "explicit synchronous staged job",
        cancellation_boundary:
          "Queued work can be cancelled before execution. Mid-request cancellation is not configured.",
        classification: "NON-PRODUCTION PHASE 2 VALIDATION EVIDENCE",
        resource_safety_limits: {
          maximum_plan_assignments: 1000,
          maximum_calibration_observations: 1000,
          maximum_verification_upload_bytes: 10485760,
        },
        disclaimer:
          "Deterministic software evidence only; not field or scientific validation.",
      },
    }),
  );
  await page.route("**/api/phase2-validation-bundles/?incident=*", (route) =>
    route.fulfill({
      json: { count: 0, next: null, previous: null, results: [] },
    }),
  );
  await page.route("**/api/terrain-analysis-status/", (route) =>
    route.fulfill({
      json: {
        provider: {
          provider: "disabled",
          provider_version: "",
          dataset_product: "No terrain profile source configured",
          dataset_version: "",
          horizontal_crs: "EPSG:4326",
          vertical_crs: "unknown",
          target_vertical_crs: "unknown",
          resolution_m: null,
          license_terms_url: "",
          permitted_use: "No terrain profile source is enabled.",
          coverage: {},
          source_content_sha256: "",
          offline: true,
        },
        provider_configuration: {},
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
            interpretation:
              "Resource-safety bounds, not validated operational capacity.",
          },
          disclaimer: "Planning estimate only.",
        },
        configured: false,
        approved_for_analysis: false,
        available: false,
        execution_model: "explicit synchronous staged job",
        cancellation_boundary: "Queued work can be cancelled before execution.",
        resource_safety_limits: {
          maximum_distance_m: 200000,
          maximum_samples: 1001,
        },
        warning: "No terrain profile provider is configured.",
        classification: "NON-PRODUCTION P3.1 TERRAIN DECISION SUPPORT",
        disclaimer: "Planning estimate only.",
      },
    }),
  );
  await page.route("**/api/terrain-analyses/?incident=*", (route) =>
    route.fulfill({
      json: { count: 0, next: null, previous: null, results: [] },
    }),
  );
  await page.route("**/api/field-observations/?incident=*", (route) =>
    route.fulfill({
      json: {
        count: fieldObservationCreated ? 1 : 0,
        next: null,
        previous: null,
        results: fieldObservationCreated ? [fieldObservation()] : [],
      },
    }),
  );
  await page.route("**/api/field-observations/", async (route) => {
    expect(route.request().method()).toBe("POST");
    expect(route.request().postDataJSON()).toMatchObject({
      incident: "syn-1",
      infrastructure_rf_input_snapshot: "rf-snapshot-1",
      subscriber_rf_input_snapshot: "rf-snapshot-2",
      classification: "good",
      evidence_type: "measured",
      location_precision: "redacted",
      latitude: null,
      longitude: null,
      location_precision_m: null,
      observer_source: "Synthetic exercise team",
      collection_method: "Scripted field check",
      measurements: {
        measured_distance_m: "1000",
        predicted_distance_m: "900",
      },
    });
    fieldObservationCreated = true;
    return route.fulfill({ json: fieldObservation() });
  });
  await page.route(
    "**/api/field-observations/observation-1/review/",
    async (route) => {
      expect(route.request().postDataJSON()).toEqual({
        decision: "approved",
        reason: "Synthetic review reason",
      });
      fieldObservationApproved = true;
      return route.fulfill({ json: fieldObservation() });
    },
  );
  await page.route("**/api/calibration-sets/?incident=*", (route) =>
    route.fulfill({
      json: {
        count: calibrationCreated ? 1 : 0,
        next: null,
        previous: null,
        results: calibrationCreated ? [calibrationSet()] : [],
      },
    }),
  );
  await page.route("**/api/calibration-sets/", async (route) => {
    expect(route.request().method()).toBe("POST");
    expect(route.request().postDataJSON()).toEqual({
      incident: "syn-1",
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
    calibrationCreated = true;
    return route.fulfill({ json: calibrationSet() });
  });
  await page.route("**/api/channel-imports/", (route) =>
    route.fulfill({
      json: {
        valid: true,
        dry_run: true,
        approval_required: false,
        would_create: { releases: 1 },
        errors: [],
      },
    }),
  );
  await page.goto("/");
  await expectNoAccessibilityViolations(page, testInfo, "sign-in-desktop");
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Username")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Password")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Sign in" })).toBeFocused();
  await page.getByLabel("Username").fill("admin");
  await page.getByLabel("Password").fill("synthetic-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(
    page.getByRole("button", { name: /^Synthetic Flood Exercise/ }),
  ).toBeVisible();
  const workspaceLogo = page.getByRole("img", {
    name: "Texas Communications Unit (TX-COMU) logo",
  });
  await expect(workspaceLogo).toBeVisible();
  await expect(page.locator("picture.brand-mark source")).toHaveAttribute(
    "srcset",
    "/brand/tx-comu-logo-transparent.svg",
  );
  await expect(page.getByText("ICT Toolkit", { exact: true })).toBeVisible();
  const planningMap = page.getByRole("region", {
    name: "Radio site planning map",
  });
  await expect(planningMap).toBeVisible();
  await expect(planningMap).toHaveAccessibleDescription(
    /Keyboard and screen-reader users can use the coordinate form/,
  );
  await page.evaluate(() => (document.activeElement as HTMLElement)?.blur());
  await page.keyboard.press("Tab");
  const skipLink = page.getByRole("link", {
    name: "Skip to planning workspace",
  });
  await expect(skipLink).toBeFocused();
  await skipLink.press("Enter");
  await expect(page.locator("#main-content")).toBeFocused();
  await expect(page.getByText(/P3.1 Terrain Prototype/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "ICS-205" })).toBeVisible();
  await expect(
    page.getByText("SYN CALL", { exact: true }).first(),
  ).toBeVisible();
  await expect(
    page.getByText("Synthetic Command Site", { exact: true }).first(),
  ).toBeVisible();
  const coverageWorkspace = page.getByRole("region", {
    name: "Band and environment estimates",
  });
  await expect(
    coverageWorkspace.getByText("fspl-horizon-v1-provisional", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    coverageWorkspace.getByText(
      "Provisional configuration—practitioner review required",
      { exact: true },
    ),
  ).toBeVisible();
  const deconflictionWorkspace = page.getByRole("region", {
    name: "Frequency deconfliction review",
  });
  await expect(
    deconflictionWorkspace.getByText(
      "Reviewed ruleset—integrated validation and allowlisting required",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(
    deconflictionWorkspace.getByText(/differences never suppress/i),
  ).toBeVisible();
  const rfWorkspace = page.getByRole("region", {
    name: "Subscriber RF profiles",
  });
  await expect(rfWorkspace).toBeVisible();
  await expect(
    rfWorkspace.getByText(/synthetic or explicitly approved data only/i),
  ).toBeVisible();
  await rfWorkspace.getByText("Create subscriber profile").click();
  const createProfile = rfWorkspace.locator("details.rf-create-profile");
  await createProfile
    .getByLabel("Profile name")
    .fill("Synthetic Portable Assumption");
  await createProfile.getByLabel("Profile type").selectOption("portable");
  await createProfile
    .getByLabel("Description")
    .fill("Synthetic exercise values only");
  await createProfile
    .getByRole("button", { name: "Create profile and draft" })
    .click();
  await expect(
    rfWorkspace.getByRole("option", {
      name: "Synthetic Portable Assumption · Portable",
    }),
  ).toBeAttached();
  await rfWorkspace.getByLabel("Transmit frequency (Hz)").fill("155000000");
  await rfWorkspace.getByLabel("Transmitter power (W)").fill("5.2500");
  await rfWorkspace
    .getByLabel("Effective radiated power (ERP) (W)")
    .fill("7.1000");
  await rfWorkspace.getByLabel("ERP source").selectOption("entered");
  await rfWorkspace.getByLabel("Antenna gain (dB)").fill("2.15");
  await rfWorkspace.getByLabel("Feed-line loss (dB)").fill("0.30");
  await rfWorkspace.getByLabel("Antenna center AGL (m)").fill("12.50");
  await rfWorkspace.getByLabel("Emission bandwidth (Hz)").fill("11200");
  await rfWorkspace
    .getByLabel("Input basis")
    .selectOption("modeled_assumption");
  await rfWorkspace
    .getByLabel("Notes")
    .fill("Synthetic modeled assumptions for browser verification");
  await rfWorkspace.getByRole("button", { name: "Save RF draft" }).click();
  await expect.poll(() => rfInputs.transmitter_power_w).toBe("5.2500");
  expect(rfInputs.tx_frequency_hz).toBe(155000000);
  expect(rfInputs.rx_frequency_hz).toBeNull();
  page.once("dialog", (dialog) => dialog.accept());
  await rfWorkspace
    .getByRole("button", { name: "Approve and lock RF version" })
    .click();
  await expect(
    rfWorkspace.getByText("Server calculation path and immutable provenance"),
  ).toBeVisible();
  await rfWorkspace.getByLabel("Snapshot label").fill("Synthetic RF baseline");
  await rfWorkspace
    .getByRole("button", { name: "Create immutable snapshot" })
    .click();
  await expect(
    rfWorkspace.getByText("Synthetic RF baseline", { exact: true }).last(),
  ).toBeVisible();
  await expect(rfWorkspace.getByText("b".repeat(64))).toBeVisible();
  const haatWorkspace = page.getByRole("region", {
    name: "Elevation and HAAT",
  });
  await expect(
    haatWorkspace.getByText("ICT Toolkit deterministic terrain fixture (flat)"),
  ).toBeVisible();
  await haatWorkspace
    .getByRole("button", {
      name: "Refresh sites, RF snapshots, and source status",
    })
    .click();
  await haatWorkspace.getByLabel("Radio site").selectOption("site-1");
  await haatWorkspace
    .getByLabel("Approved RF input snapshot with antenna AGL")
    .selectOption("rf-snapshot-1");
  await haatWorkspace
    .getByRole("button", { name: "Calculate elevation and HAAT" })
    .click();
  await expect(
    haatWorkspace.getByText("12.500 m", { exact: true }),
  ).toBeVisible();
  await expect(
    haatWorkspace.getByText("Synthetic fixture only."),
  ).toBeVisible();
  await haatWorkspace
    .getByRole("button", { name: "Retry with fresh elevation data" })
    .click();
  page.once("dialog", (dialog) => dialog.accept());
  await haatWorkspace
    .getByRole("button", { name: "Approve and lock result" })
    .click();
  await expect(
    haatWorkspace.getByText("approved", { exact: true }),
  ).toBeVisible();
  const calibrationWorkspace = page.getByRole("region", {
    name: "Field observations and local calibration",
  });
  await expect(
    calibrationWorkspace.getByText(
      "Provisional method—RF/privacy review required",
      { exact: true },
    ),
  ).toBeVisible();
  await calibrationWorkspace
    .getByLabel("Infrastructure RF snapshot")
    .selectOption("rf-snapshot-1");
  await calibrationWorkspace
    .getByLabel("Subscriber RF snapshot")
    .selectOption("rf-snapshot-2");
  await calibrationWorkspace
    .getByLabel("Location handling")
    .selectOption("redacted");
  await calibrationWorkspace
    .getByLabel("Observer or source")
    .fill("Synthetic exercise team");
  await calibrationWorkspace
    .getByLabel("Collection method")
    .fill("Scripted field check");
  await calibrationWorkspace.getByLabel("Measured distance (m)").fill("1000");
  await calibrationWorkspace.getByLabel("Predicted distance (m)").fill("900");
  await calibrationWorkspace
    .getByRole("button", { name: "Record immutable observation" })
    .click();
  await expect(
    calibrationWorkspace.getByRole("table", {
      name: "Field observation history",
    }),
  ).toContainText("pending");
  page.once("dialog", (dialog) => dialog.accept("Synthetic review reason"));
  await calibrationWorkspace
    .getByRole("button", { name: "Approve evidence" })
    .click();
  await calibrationWorkspace
    .getByLabel(/good · 1000 m measured \/ 900 m predicted/i)
    .check();
  await calibrationWorkspace
    .getByRole("button", { name: "Calculate transparent comparison" })
    .click();
  const calibrationTable = calibrationWorkspace.getByRole("table", {
    name: "Calibration set history",
  });
  await expect(calibrationTable).toContainText("1.100× distance");
  await expect(calibrationTable).toContainText("100.0 m → 10.0 m");
  await expect(calibrationTable).toContainText("Incident-local · not promoted");
  const phase2ValidationWorkspace = page.getByRole("region", {
    name: "End-to-end validation bundle",
  });
  await expect(phase2ValidationWorkspace).toBeVisible();
  await expect(
    phase2ValidationWorkspace.getByText("phase-2-validation-v1-provisional", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    phase2ValidationWorkspace.getByText(
      "Fail closed — qualified review still required",
      { exact: true },
    ),
  ).toBeVisible();
  const terrainWorkspace = page.getByRole("region", {
    name: "Terrain profile analysis",
  });
  await expect(terrainWorkspace).toBeVisible();
  await expect(
    terrainWorkspace.getByText("fail closed", { exact: true }),
  ).toBeVisible();
  await expect(
    terrainWorkspace.getByRole("button", { name: "Queue terrain profile" }),
  ).toBeDisabled();
  await expect(
    terrainWorkspace.getByText(/Core planning remains available/),
  ).toBeVisible();
  await page
    .getByLabel("Coordinate", { exact: true })
    .fill("33° 12′ 52.20″ N, 97° 07′ 59.16″ W");
  await page.getByRole("button", { name: "Parse and preview" }).click();
  await expect(
    page.getByText("14SQB7401876781", { exact: true }).first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Approve and lock revision" }).click();
  await expect(
    page.getByRole("button", { name: "Download official PDF" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "SVG map" })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Channel library" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Validate dry run" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "Validation passed" }),
  ).toContainText("Validation passed");
  await expect(
    page.getByText(/Originally developed by the Texas Communications Unit/),
  ).toBeVisible();
  await expect(
    page.getByText(/TX-COMU names, logos, and identifying marks/),
  ).toBeVisible();
  await expectNoAccessibilityViolations(
    page,
    testInfo,
    "authenticated-workspace-desktop",
  );
  const desktopScreenshot = testInfo.outputPath(
    "branded-workspace-desktop.png",
  );
  await page.screenshot({ path: desktopScreenshot, fullPage: true });
  await testInfo.attach("branded-workspace-desktop", {
    path: desktopScreenshot,
    contentType: "image/png",
  });

  await page.setViewportSize({ width: 320, height: 720 });
  await expect(
    page.getByRole("heading", { name: "ICT Branch Toolkit" }),
  ).toBeVisible();
  await expect(page.getByText(/P3.1 Terrain Prototype/)).toBeVisible();
  await expectDocumentReflow(page);
  await expectNoAccessibilityViolations(
    page,
    testInfo,
    "authenticated-workspace-320-css-pixels",
  );
  const mobileScreenshot = testInfo.outputPath("branded-workspace-mobile.png");
  await page.screenshot({ path: mobileScreenshot, fullPage: true });
  await testInfo.attach("branded-workspace-mobile", {
    path: mobileScreenshot,
    contentType: "image/png",
  });
});
