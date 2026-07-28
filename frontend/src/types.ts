export interface OperationalPeriod {
  id: string;
  name: string;
  starts_at: string;
  ends_at: string;
}

export interface Incident {
  id: string;
  name: string;
  incident_number: string;
  status: "planning" | "active" | "closed";
  operational_periods: OperationalPeriod[];
  archived_at: string | null;
  permissions: string[];
}

export interface CurrentUser {
  username: string;
  display_name: string;
  role:
    "administrator" | "coml" | "comc" | "comt" | "contributor" | "read_only";
  permissions: string[];
}

export interface ResourceSource {
  id: string;
  slug: string;
  name: string;
  source_type: string;
  authoritative_url: string;
}

export interface ResourceRelease {
  id: string;
  source: ResourceSource;
  version: string;
  released_on: string | null;
  effective_status: "draft" | "effective" | "superseded";
  content_sha256: string;
  document_title: string;
  publisher: string;
  retrieved_on: string | null;
  permitted_use: string;
  transformation_method: string;
  imported_at: string;
}

export interface ConventionalChannel {
  id: string;
  release: ResourceRelease;
  identifier: string;
  name: string;
  channel_use: string;
  band: string;
  jurisdiction: string;
  rx_frequency_hz: number;
  tx_frequency_hz: number | null;
  bandwidth_hz: number | null;
  mode: string;
  rx_squelch: string;
  tx_squelch: string;
  emission_designator: string;
  eligibility: string;
  authorization: string;
  source_section: string;
  source_pages: string;
  restrictions: string;
  notes: string;
  is_active: boolean;
}

export interface TrunkedTalkgroup {
  id: string;
  release: ResourceRelease;
  identifier: string;
  name: string;
  system_name: string;
  talkgroup_id: number;
  mode: string;
  eligibility: string;
  authorization: string;
  source_section: string;
  source_pages: string;
  restrictions: string;
  notes: string;
  is_active: boolean;
}

export interface ImportError {
  path: string;
  code: string;
  message: string;
}

export interface ImportResult {
  valid: boolean;
  dry_run: boolean;
  approval_required?: boolean;
  would_create?: Record<string, number>;
  created?: Record<string, number>;
  errors: ImportError[];
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface PlanAssignment {
  id: string;
  revision: string;
  position: number;
  function: string;
  channel_name: string;
  assignment: string;
  rx_frequency_hz: number | null;
  rx_squelch: string;
  tx_frequency_hz: number | null;
  tx_squelch: string;
  mode: string;
  remarks: string;
  structured_note: "" | "remote_base" | "link" | "patch" | "other";
  contact_name: string;
  site_address: string;
  phone_numbers: string;
  contact_24_hour: string;
  resource_snapshot: Record<string, unknown>;
}

export interface PlanRelationship {
  id: string;
  revision: string;
  relationship_type: "remote_base" | "link" | "patch";
  label: string;
  assignments: string[];
}

export interface PlanRevision {
  id: string;
  plan: string;
  number: number;
  status: "draft" | "approved";
  is_locked: boolean;
  prepared_by_name: string;
  prepared_by_position: string;
  approved_at: string | null;
  assignments: PlanAssignment[];
  relationships: PlanRelationship[];
}

export interface ICS205Plan {
  id: string;
  incident: string;
  operational_period: string;
  title: string;
  revisions: PlanRevision[];
}

export interface RevisionComparison {
  revision: number;
  other_revision: number;
  changes: {
    key: string;
    before: string | null;
    after: string | null;
    changed_fields: string[];
  }[];
}

export interface CoordinateParseResult {
  latitude: number;
  longitude: number;
  input_format: "decimal" | "ddm" | "dms" | "mgrs";
  formats: Record<"decimal" | "ddm" | "dms" | "mgrs", string>;
}

export interface ManualRing {
  id: string;
  site: string;
  ring_type: "operational" | "fringe" | "coordination";
  radius_m: number;
  label: string;
}

export interface RadioSite {
  id: string;
  incident: string;
  name: string;
  description: string;
  latitude: string;
  longitude: string;
  entered_coordinate: string;
  coordinate_format: "map" | "decimal" | "ddm" | "dms" | "mgrs" | "address";
  coordinate_formats: Record<"decimal" | "ddm" | "dms" | "mgrs", string>;
  address: string;
  source_identity: string;
  source_retrieved_at: string | null;
  rings: ManualRing[];
}

export interface SiteAssignment {
  id: string;
  site: string;
  site_name: string;
  assignment: string;
  assignment_label: string;
  site_snapshot: Record<string, unknown>;
}

export interface GeocoderSearchResult {
  provider: string;
  configured: boolean;
  results: {
    label: string;
    latitude: number;
    longitude: number;
    provider: string;
  }[];
}

export type SubscriberProfileType =
  "portable" | "mobile" | "fixed" | "cache" | "gateway" | "configurable";

export type ERPSource = "unknown" | "entered" | "calculated";
export type AntennaGainReference = "unknown" | "dbi" | "dbd";
export type Polarization =
  "unknown" | "vertical" | "horizontal" | "circular" | "mixed";
export type FrequencyBand =
  "unknown" | "vhf_low" | "vhf_high" | "uhf" | "700" | "800" | "900" | "other";
export type MountingType =
  "unknown" | "handheld" | "vehicle" | "structure" | "tower" | "mast" | "other";
export type RFInputBasis =
  "unknown" | "recorded_fact" | "modeled_assumption" | "mixed";

export interface RFInputFields {
  tx_frequency_hz: number | null;
  rx_frequency_hz: number | null;
  transmitter_power_w: string | null;
  effective_radiated_power_w: string | null;
  erp_source: ERPSource;
  receiver_sensitivity_dbm: string | null;
  antenna_model: string | null;
  antenna_gain_db: string | null;
  antenna_gain_reference: AntennaGainReference;
  feed_line_type: string | null;
  feed_line_length_m: string | null;
  feed_line_loss_db: string | null;
  additional_system_loss_db: string | null;
  polarization: Polarization;
  frequency_band: FrequencyBand;
  emission_designator: string | null;
  emission_bandwidth_hz: number | null;
  mounting_type: MountingType;
  antenna_center_agl_m: string | null;
  antenna_center_amsl_m: string | null;
  haat_m: string | null;
  input_basis: RFInputBasis;
  notes: string | null;
  erp_calculation_path: Record<string, unknown> | null;
  input_snapshot: Record<string, unknown> | null;
  input_sha256: string | null;
}

export type EditableRFInputFields = Omit<
  RFInputFields,
  "erp_calculation_path" | "input_snapshot" | "input_sha256"
>;

export interface SubscriberProfile {
  id: string;
  incident: string;
  name: string;
  profile_type: SubscriberProfileType;
  description: string;
  archived_at: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface SubscriberProfileVersion extends RFInputFields {
  id: string;
  profile: string;
  number: number;
  status: "draft" | "approved";
  is_locked: boolean;
  approved_at: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface RFAnalysisInputSnapshot {
  id: string;
  incident: string;
  profile_version: string;
  profile_name: string;
  profile_type: SubscriberProfileType;
  profile_version_number: number;
  label: string;
  input_snapshot: Record<string, unknown>;
  input_sha256: string;
  created_at?: string;
}

export interface CreateSubscriberProfilePayload {
  incident: string;
  name: string;
  profile_type: SubscriberProfileType;
  description: string;
  initial_version: EditableRFInputFields;
}

export interface UpdateSubscriberProfilePayload {
  name?: string;
  profile_type?: SubscriberProfileType;
  description?: string;
}

export interface ElevationProviderStatus {
  provider: string;
  dataset_product: string;
  horizontal_crs: string;
  vertical_crs: string;
  target_vertical_crs: string;
  resolution_m: string | null;
  source_version: string;
  license_terms_url: string;
  permitted_use: string;
  coverage: Record<string, unknown>;
  source_content_sha256: string;
  offline: boolean;
  configured: boolean;
  approved: boolean;
  available: boolean;
  warning: string;
}

export type ElevationState =
  "complete" | "partial" | "missing" | "out_of_coverage" | "stale";

export interface ElevationSnapshot {
  id: string;
  incident: string;
  site: string;
  query_sha256: string;
  provider: string;
  dataset_product: string;
  horizontal_crs: string;
  vertical_crs: string;
  target_vertical_crs: string;
  resolution_m: string | null;
  source_version: string;
  source_retrieved_at: string | null;
  license_terms_url: string;
  permitted_use: string;
  coverage: Record<string, unknown>;
  source_content_sha256: string;
  acquisition_state: Exclude<ElevationState, "stale">;
  current_state: ElevationState;
  sample_sha256: string;
  transformation: Record<string, unknown>;
  warnings: string[];
  retrieved_at: string;
  stale_at: string | null;
}

export interface HAATCalculation {
  id: string;
  incident: string;
  site: string;
  site_name: string;
  profile_version: string;
  profile_name: string;
  profile_version_number: number;
  rf_input_snapshot: string;
  rf_input_label: string;
  elevation_snapshot: string;
  elevation: ElevationSnapshot;
  supersedes: string | null;
  status: "draft" | "approved";
  calculation_state: "complete" | "partial" | "unavailable";
  method: string;
  method_version: string;
  radial_count: number;
  start_azimuth_deg: string;
  sampling_interval_m: number;
  inner_distance_m: number;
  outer_distance_m: number;
  rounding_m: string;
  antenna_agl_m: string;
  site_elevation_m: string | null;
  antenna_amsl_m: string | null;
  average_terrain_m: string | null;
  haat_m: string | null;
  sample_count: number;
  excluded_sample_count: number;
  algorithm_snapshot: Record<string, unknown>;
  exclusions: Record<string, unknown>[];
  warnings: string[];
  result_snapshot: Record<string, unknown>;
  result_sha256: string;
  approved_at: string | null;
  created_at: string;
  is_locked: boolean;
}

export interface CreateHAATCalculationPayload {
  site: string;
  rf_input_snapshot: string;
  radial_count: number;
  start_azimuth_deg: string;
  sampling_interval_m: number;
  inner_distance_m: number;
  outer_distance_m: number;
  rounding_m: string;
  force_refresh: boolean;
}

export interface CoverageEngineStatus {
  engine: string;
  engine_version: string;
  approved_for_operational_use: boolean;
  approved_presets: { preset: string; preset_version: string }[];
  disclaimer: string;
  supported_band_groups: {
    name: string;
    lower_hz: number;
    upper_hz: number;
  }[];
  environments: {
    name: string;
    additional_margin_db: string;
  }[];
  presets: Record<
    string,
    {
      version: string;
      fade_margin_db: string;
      uncertainty_db: string;
      receiver_height_m: string;
      maximum_distance_m: number;
      distance_rounding_m: number;
    }
  >;
}

export interface CoverageEstimate {
  id: string;
  incident: string;
  site: string;
  site_name: string;
  rf_input_snapshot: string;
  rf_input_label: string;
  haat_calculation: string;
  haat_result_sha256: string;
  status: "draft" | "approved";
  calculation_state: "complete" | "unsupported";
  environment: "open" | "rural" | "suburban" | "urban" | "dense_urban";
  band: string;
  engine: string;
  engine_version: string;
  preset: string;
  preset_version: string;
  center_latitude: string;
  center_longitude: string;
  nominal_distance_m: number | null;
  conservative_distance_m: number | null;
  optimistic_distance_m: number | null;
  input_snapshot: Record<string, unknown>;
  input_sha256: string;
  model_snapshot: Record<string, unknown>;
  warnings: string[];
  exclusions: { code: string; reason: string }[];
  explanation: string;
  result_snapshot: Record<string, unknown>;
  result_sha256: string;
  approved_at: string | null;
  created_at: string;
  is_locked: boolean;
}

export interface CreateCoverageEstimatePayload {
  haat_calculation: string;
  environment: CoverageEstimate["environment"];
  preset: string;
}

export interface DirectionalAnalysisStatus {
  rule_version: string;
  approved_for_operational_use: boolean;
  rule: string;
  disclaimer: string;
  supported_profile_types: SubscriberProfileType[];
}

export interface DirectionalCoverageAnalysis {
  id: string;
  incident: string;
  site: string;
  site_name: string;
  infrastructure_rf_input_snapshot: string;
  infrastructure_label: string;
  subscriber_rf_input_snapshot: string;
  subscriber_label: string;
  subscriber_profile_name: string;
  subscriber_profile_type: SubscriberProfileType;
  haat_calculation: string;
  haat_result_sha256: string;
  status: "draft" | "approved";
  calculation_state: "complete" | "unsupported" | "no_overlap";
  environment: CoverageEstimate["environment"];
  engine: string;
  engine_version: string;
  preset: string;
  preset_version: string;
  rule_version: string;
  center_latitude: string;
  center_longitude: string;
  talk_out_distance_m: number | null;
  talk_in_distance_m: number | null;
  probable_two_way_distance_m: number | null;
  limiting_path: "talk_out" | "talk_in" | "equal" | "none";
  input_snapshot: Record<string, unknown>;
  input_sha256: string;
  model_snapshot: Record<string, unknown>;
  warnings: string[];
  exclusions: { code: string; reason: string }[];
  explanation: string;
  result_snapshot: Record<string, unknown>;
  result_sha256: string;
  approved_at: string | null;
  created_at: string;
  is_locked: boolean;
}

export interface CreateDirectionalCoverageAnalysisPayload {
  haat_calculation: string;
  subscriber_rf_input_snapshot: string;
  environment: CoverageEstimate["environment"];
  preset: string;
}
