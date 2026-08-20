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
    | "administrator"
    | "coml"
    | "comc"
    | "comt"
    | "auxcomm"
    | "incm"
    | "contributor"
    | "read_only";
  permissions: string[];
}

export type ToolkitRole = CurrentUser["role"];

export interface LocalContingencyAccount {
  username: string;
  display_name: string;
  email: string;
  role: ToolkitRole;
  is_active: boolean;
  linked_to_external_identity: boolean;
  reason: string;
  must_change_password: boolean;
  disabled_at: string | null;
  disabled_reason: string;
  created_at: string;
  updated_at: string;
  temporary_password?: string;
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

export type AssignmentOperatingClassification =
  | "fixed_pair"
  | "transmit_only"
  | "receive_only"
  | "named_system"
  | "dynamic_pool"
  | "not_determined";

export type AssignmentTechnologySubtype =
  "" | "trunked_talkgroup" | "lte_5g" | "scada" | "spread_spectrum" | "other";

export interface PlanAssignment {
  id: string;
  revision: string;
  position: number;
  function: string;
  channel_name: string;
  assignment: string;
  operating_classification: AssignmentOperatingClassification;
  technology_subtype: AssignmentTechnologySubtype;
  subscriber_profile_version: string | null;
  rx_frequency_hz: number | null;
  rx_squelch: string;
  tx_frequency_hz: number | null;
  tx_squelch: string;
  mode: string;
  remarks: string;
  structured_note: "" | "remote_base" | "link" | "patch" | "other";
  contact_name?: string;
  site_address?: string;
  phone_numbers?: string;
  contact_24_hour?: string;
  published_contact_fields: (
    "contact_name" | "site_address" | "phone_numbers" | "contact_24_hour"
  )[];
  contact_publication_purpose: string;
  contact_publication_placement: "remarks" | "special_instructions";
  collaboration_version: number;
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
  copied_from: string | null;
  approved_at: string | null;
  collaboration_version: number;
  assignments: PlanAssignment[];
  relationships: PlanRelationship[];
}

export interface PlanPublicationSummary {
  digest: string;
  has_published_contacts: boolean;
  contact_publications: {
    assignment_id: string;
    position: number;
    channel_name: string;
    purpose: string;
    placement: "remarks" | "special_instructions";
    fields: string[];
    values: Record<string, string>;
  }[];
}

export interface ICS205Plan {
  id: string;
  incident: string;
  operational_period: string;
  title: string;
  revisions: PlanRevision[];
}

export interface ExtensionCapability {
  id: string;
  name: string;
  kind: "tool" | "report";
  required_permission: "extension.run";
  scope: "incident_revision";
  inputs: Record<string, unknown>;
  outputs: {
    schema: string;
    classification: "draft" | "decision_support" | "official";
  };
  validation: string;
  audit: string;
  export: {
    formats: string[];
    deterministic: boolean;
  };
}

export interface ExtensionManifest {
  key: string;
  name: string;
  description: string;
  version: string;
  contract_version: string;
  provider: string;
  capabilities: ExtensionCapability[];
  source_records: string[];
  approval_requirements: string;
  sensitivity: string;
  retention: string;
  failure_isolation: string;
  accessibility: string;
  official_output: false;
}

export interface ExtensionCatalogEntry {
  manifest: ExtensionManifest;
  installed: boolean;
  enabled: boolean;
  compatible: boolean;
  installation_id: string | null;
  operator_message: string;
}

export interface ExtensionExecution {
  id: string;
  extension_key: string;
  extension_version: string;
  contract_version: string;
  capability: string;
  capability_kind: "tool" | "report";
  incident: string;
  source_revision: string;
  source_revision_number: number;
  input_snapshot: Record<string, unknown>;
  input_sha256: string;
  result_snapshot: Record<string, unknown>;
  result_sha256: string;
  output_classification: "draft" | "decision_support" | "official";
  status: "complete" | "failed";
  failure_code: string;
  failure_message: string;
  created_by: number;
  created_at: string;
}

export interface CreateExtensionExecutionPayload {
  extension_key: string;
  contract_version: string;
  capability: string;
  incident: string;
  source_revision: string;
  inputs: {
    minimum_assignment_count: number;
  };
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

export type CollaborationOperation =
  | "revision.update"
  | "assignment.create"
  | "assignment.update"
  | "assignment.delete"
  | "assignment.reorder";

export interface CollaborationMutationPayload {
  client_mutation_id: string;
  device_id: string;
  revision: string;
  operation: CollaborationOperation;
  object_id?: string | null;
  section: string;
  base_version: number;
  changes: Record<string, unknown>;
}

export interface CollaborationResolution {
  id: string;
  decision: "discard" | "reapply" | "replace";
  explanation: string;
  replacement_change: string | null;
  resolved_by: number;
  created_at: string;
}

export interface CollaborationChange {
  id: string;
  client_mutation_id: string;
  revision: string;
  actor: number;
  actor_display_name: string;
  device_id: string;
  operation: CollaborationOperation;
  object_id: string | null;
  section: string;
  base_version: number;
  resulting_version: number | null;
  affected_fields: string[];
  proposed_snapshot: Record<string, unknown>;
  current_snapshot: Record<string, unknown>;
  payload_sha256: string;
  disposition: "saved" | "conflict" | "rejected";
  result: Record<string, unknown>;
  resolution: CollaborationResolution | null;
  created_at: string;
}

export interface CollaborationPresence {
  id: string;
  revision: string;
  section: string;
  mode: "viewing" | "editing";
  object_id: string | null;
  field_name: string;
  display_name: string;
  incident_role: string;
  is_current_user: boolean;
}

export interface ExternalIdentityStatus {
  provider: string;
  enabled: boolean;
  protocol: "authorization_code";
  authorization_code_flow: boolean;
  password_passthrough: boolean;
  live_connection: boolean;
  warning: string;
  break_glass_local_login_available: boolean;
  eligibility_group: string;
  role_field: string;
  identity_refresh_seconds: number;
  outage_grace_seconds: number;
  allowed_roles: ToolkitRole[];
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
  tx_access_code: string;
  rx_access_code: string;
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
  archived_at?: string | null;
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

export interface CalibrationStatus {
  algorithm: string;
  algorithm_version: string;
  approved_for_operational_use: boolean;
  minimum_usable_observations: number;
  ratio_bounds: {
    minimum: string;
    maximum: string;
  };
  location_rule: string;
  promotion_rule: string;
  disclaimer: string;
}

export interface FieldObservationReview {
  id: string;
  observation: string;
  decision: "approved" | "excluded";
  reason: string;
  evidence_sha256: string;
  reviewed_by: number;
  created_at: string;
}

export interface FieldObservation {
  id: string;
  incident: string;
  infrastructure_rf_input_snapshot: string;
  infrastructure_label: string;
  subscriber_rf_input_snapshot: string;
  subscriber_label: string;
  coverage_estimate: string | null;
  directional_analysis: string | null;
  supersedes: string | null;
  superseded_by: string | null;
  classification: "good" | "marginal" | "failed";
  evidence_type: "measured" | "operator" | "imported" | "modeled";
  observed_from: string;
  observed_to: string;
  location_precision: "exact" | "generalized" | "redacted";
  coordinate_reference: "EPSG:4326";
  latitude: string | null;
  longitude: string | null;
  location_precision_m: number | null;
  direction_degrees: string | null;
  path_distance_m: number | null;
  observer_source: string;
  collection_method: string;
  environment: Record<string, string>;
  measurements: Record<string, string>;
  notes: string;
  quality_flags: string[];
  source_record_id: string;
  source_revision: string;
  input_snapshot: Record<string, unknown>;
  input_sha256: string;
  created_by: number;
  created_at: string;
  current_review_state: "pending" | "approved" | "excluded";
  reviews: FieldObservationReview[];
}

export interface CreateFieldObservationPayload {
  incident: string;
  infrastructure_rf_input_snapshot: string;
  subscriber_rf_input_snapshot: string;
  coverage_estimate?: string | null;
  directional_analysis?: string | null;
  supersedes?: string | null;
  classification: FieldObservation["classification"];
  evidence_type: FieldObservation["evidence_type"];
  observed_from: string;
  observed_to: string;
  location_precision: FieldObservation["location_precision"];
  latitude?: string | null;
  longitude?: string | null;
  location_precision_m?: number | null;
  direction_degrees?: string | null;
  path_distance_m?: number | null;
  observer_source: string;
  collection_method: string;
  environment: Record<string, string>;
  measurements: Record<string, string>;
  notes: string;
  quality_flags: string[];
  source_record_id: string;
  source_revision: string;
}

export interface CalibrationSet {
  id: string;
  incident: string;
  name: string;
  version: number;
  status: "draft" | "approved";
  calculation_state: "complete" | "insufficient_data";
  algorithm: string;
  algorithm_version: string;
  parameters: Record<string, string | number>;
  baseline_preset: string;
  baseline_preset_version: string;
  observation_ids: string[];
  observation_snapshot: Record<string, unknown>[];
  observation_sha256: string;
  recommended_preset: {
    schema_version: string;
    base_preset: string;
    base_preset_version: string;
    distance_multiplier: string | null;
    scope: "incident_local";
    promotion_state: "not_promoted";
    organization_default_overwritten: false;
  };
  before_after: {
    before: {
      mean_absolute_error_m: string;
      mean_absolute_percentage_error: string;
    } | null;
    after: {
      mean_absolute_error_m: string;
      mean_absolute_percentage_error: string;
    } | null;
  };
  warnings: string[];
  exclusions: {
    observation_id: string;
    code: string;
    reason: string;
  }[];
  result_snapshot: Record<string, unknown>;
  result_sha256: string;
  approved_at: string | null;
  created_at: string;
  is_locked: boolean;
}

export interface CreateCalibrationSetPayload {
  incident: string;
  name: string;
  observations: string[];
  baseline_preset: string;
  baseline_preset_version: string;
  parameters: {
    minimum_samples: number;
    minimum_ratio: string;
    maximum_ratio: string;
  };
}

export interface Phase2ValidationStatus {
  validation_profile_id: string;
  validation_profile_version: string;
  validation_method_version: string;
  approved_for_release_candidate_use: boolean;
  execution_model: string;
  cancellation_boundary: string;
  classification: string;
  resource_safety_limits: {
    maximum_plan_assignments: number;
    maximum_calibration_observations: number;
    maximum_verification_upload_bytes: number;
  };
  disclaimer: string;
}

export interface Phase2ValidationBundle {
  id: string;
  incident: string;
  approved_revision: string;
  haat_calculation: string;
  coverage_estimate: string;
  directional_analysis: string;
  calibration_set: string;
  supersedes: string | null;
  validation_profile_id: string;
  validation_profile_version: string;
  app_version: string;
  job_state: "queued" | "running" | "complete" | "failed" | "cancelled";
  progress_step: string;
  progress_percent: number;
  status: "draft" | "approved";
  input_snapshot: Record<string, unknown>;
  input_sha256: string;
  result_snapshot: Record<string, unknown>;
  result_sha256: string;
  failure_code: string;
  failure_message: string;
  created_by: number;
  approved_by: number | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  approved_at: string | null;
  updated_at: string;
  is_locked: boolean;
  is_stale: boolean;
  stale_reasons: string[];
  approval_eligible: boolean;
}

export interface CreatePhase2ValidationBundlePayload {
  incident: string;
  approved_revision: string;
  haat_calculation: string;
  coverage_estimate: string;
  directional_analysis: string;
  calibration_set: string;
}

export interface Phase2ExportVerification {
  verified: boolean;
  detail?: string;
  audit_event_id?: string;
  occurred_at?: string;
  actor_id?: number;
  byte_size?: number;
  result_sha256?: string;
}

export interface TerrainSourceStatus {
  provider: string;
  provider_version: string;
  dataset_product: string;
  dataset_version: string;
  horizontal_crs: string;
  vertical_crs: string;
  target_vertical_crs: string;
  resolution_m: string | null;
  license_terms_url: string;
  permitted_use: string;
  coverage: Record<string, unknown>;
  source_content_sha256: string;
  offline: boolean;
}

export interface TerrainEngineStatus {
  engine: string;
  engine_version: string;
  method: string;
  approved_for_operational_use: boolean;
  capabilities: {
    terrain_profile: boolean;
    sampled_line_of_sight: boolean;
    diffraction: boolean;
    clutter: boolean;
    external_network_required: boolean;
  };
  parameters: Record<string, string | number>;
  tested_limits: {
    maximum_distance_m: number;
    maximum_samples: number;
    interpretation: string;
  };
  disclaimer: string;
}

export interface TerrainAnalysisStatus {
  provider: TerrainSourceStatus;
  provider_configuration: Record<string, unknown>;
  engine: TerrainEngineStatus;
  configured: boolean;
  approved_for_analysis: boolean;
  available: boolean;
  execution_model: string;
  cancellation_boundary: string;
  resource_safety_limits: {
    maximum_distance_m: number;
    maximum_samples: number;
  };
  warning: string;
  classification: string;
  disclaimer: string;
}

export interface TerrainProfileSample {
  distance_m: number;
  azimuth_deg: string;
  latitude: string;
  longitude: string;
  state: "complete" | "missing" | "out_of_coverage";
  source_elevation_m: string | null;
  terrain_elevation_m: string | null;
  reason: string;
  visible?: boolean | null;
  curvature_drop_m?: string | null;
  receiver_slope?: string | null;
  obstruction_slope?: string | null;
}

export interface TerrainAnalysisResult {
  schema_version?: string;
  classification?: string;
  application_version?: string;
  input_sha256?: string;
  source?: Record<string, unknown>;
  algorithm?: Record<string, unknown>;
  profile?: {
    acquisition_state?: string;
    requested_distance_m?: number;
    sample_interval_m?: number;
    sample_count?: number;
    complete_sample_count?: number;
    gap_count?: number;
    edge_effect?: boolean;
    samples?: TerrainProfileSample[];
    sample_sha256?: string;
  };
  line_of_sight?: {
    continuous_clear_distance_m?: number;
    first_obstruction_or_gap_distance_m?: number | null;
    obstruction_count?: number;
    receiver_height_m?: string;
    clearance_m?: string;
    effective_earth_radius_factor?: string;
  };
  comparison?: {
    phase2_nominal_distance_m?: number | null;
    terrain_continuous_los_distance_m?: number | null;
    difference_m?: number | null;
    difference_percent?: string | null;
    material_threshold_m?: number | null;
    materially_different?: boolean | null;
    interpretation?: string;
    layer_behavior?: string;
  };
  supported_conditions?: string[];
  unsupported_conditions?: string[];
  warnings?: string[];
  exclusions?: Record<string, unknown>[];
  explanation?: string;
  disclaimer?: string;
}

export interface TerrainAnalysis {
  id: string;
  incident: string;
  site: string;
  coverage_estimate: string;
  supersedes: string | null;
  provider: string;
  provider_version: string;
  dataset_product: string;
  dataset_version: string;
  engine: string;
  engine_version: string;
  app_version: string;
  azimuth_deg: string;
  maximum_distance_m: number;
  sample_interval_m: number;
  receiver_height_m: string;
  clearance_m: string;
  job_state: "queued" | "running" | "complete" | "failed" | "cancelled";
  analysis_state: "complete" | "partial" | "unsupported" | "";
  progress_step: string;
  progress_percent: number;
  status: "draft" | "approved";
  input_snapshot: Record<string, unknown>;
  input_sha256: string;
  result_snapshot: TerrainAnalysisResult;
  result_sha256: string;
  failure_code: string;
  failure_message: string;
  created_by: number;
  approved_by: number | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  approved_at: string | null;
  updated_at: string;
  is_locked: boolean;
  is_stale: boolean;
  stale_reasons: string[];
  approval_eligible: boolean;
}

export interface CreateTerrainAnalysisPayload {
  coverage_estimate: string;
  azimuth_deg: string;
  maximum_distance_m: number;
  sample_interval_m: number;
  receiver_height_m: string;
  clearance_m: string;
}

export interface DeconflictionRuleDefinition {
  id: string;
  name: string;
  severity: "critical" | "warning" | "caution";
  summary: string;
}

export interface DeconflictionRuleSetStatus {
  rule_set_id: string;
  rule_set_version: string;
  approved_for_operational_use: boolean;
  close_frequency_threshold_hz: number;
  rules: DeconflictionRuleDefinition[];
  analysis_statuses: {
    id: string;
    name: string;
    outcome: "not_applicable" | "not_evaluated";
    summary: string;
  }[];
  access_code_source_hierarchy: string[];
  squelch_rule: string;
  disclaimer: string;
}

export interface DeconflictionComparedInput {
  id: string;
  position?: number | null;
  function?: string;
  name: string;
  assignment?: string;
  operating_classification?: AssignmentOperatingClassification;
  technology_subtype?: AssignmentTechnologySubtype;
  rx_frequency_hz: number | null;
  tx_frequency_hz: number | null;
  rx_squelch: string;
  tx_squelch: string;
  area_count?: number;
}

export interface DeconflictionWarning {
  finding_key?: string;
  rule_id: string;
  rule_name: string;
  rule_set_version: string;
  severity: DeconflictionRuleDefinition["severity"];
  blocking?: false;
  compared_inputs: DeconflictionComparedInput[];
  evidence: Record<string, unknown>;
  assumptions: string[];
  explanation: string;
  disclaimer: string;
}

export type DeconflictionFindingDispositionValue =
  | "reviewed_no_change"
  | "plan_change_required"
  | "special_accommodation_required"
  | "source_review_required";

export interface DeconflictionFindingDisposition {
  id: string;
  analysis: string;
  finding_key: string;
  rule_id: string;
  disposition: DeconflictionFindingDispositionValue;
  explanation: string;
  created_by: number;
  created_at: string;
}

export interface DeconflictionAnalysisStatus {
  status_id: string;
  status_name: string;
  outcome: "not_applicable" | "not_evaluated";
  rule_set_version: string;
  assignment: DeconflictionComparedInput;
  affected_rule_ids: string[];
  evidence: Record<string, unknown>;
  explanation: string;
  disclaimer: string;
}

export interface DeconflictionAnalysis {
  id: string;
  incident: string;
  approved_revision: string;
  revision_number: number;
  rule_set_id: string;
  rule_set_version: string;
  status: "draft" | "approved";
  input_snapshot: {
    schema_version: string;
    approved_revision: {
      id: string;
      plan_id: string;
      number: number;
      approved_at: string;
      approved_by_id: string;
    };
    close_frequency_threshold_hz?: number;
    adjacent_channel_threshold_hz?: number;
    access_code_source_hierarchy?: string[];
    assignments: Record<string, unknown>[];
    selected_active_resources?: Record<string, unknown>[];
  };
  input_sha256: string;
  result_snapshot: {
    schema_version: string;
    rule_set_id: string;
    rule_set_version: string;
    input_sha256: string;
    rule_definitions: DeconflictionRuleDefinition[];
    analysis_status_definitions?: DeconflictionRuleSetStatus["analysis_statuses"];
    warning_count: number;
    warnings: DeconflictionWarning[];
    analysis_status_count?: number;
    analysis_statuses?: DeconflictionAnalysisStatus[];
    disclaimer: string;
  };
  result_sha256: string;
  warning_count: number;
  created_by: number;
  approved_by: number | null;
  approved_at: string | null;
  created_at: string;
  is_locked: boolean;
  finding_dispositions: DeconflictionFindingDisposition[];
}

export interface CreateDeconflictionAnalysisPayload {
  incident: string;
  approved_revision: string;
}

export interface CreateDeconflictionFindingDispositionPayload {
  finding_key: string;
  disposition: DeconflictionFindingDispositionValue;
  explanation: string;
}
