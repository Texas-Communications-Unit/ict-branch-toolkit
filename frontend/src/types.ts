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
  imported_at: string;
}

export interface ConventionalChannel {
  id: string;
  release: ResourceRelease;
  identifier: string;
  name: string;
  band: string;
  rx_frequency_hz: number;
  tx_frequency_hz: number | null;
  mode: string;
  restrictions: string;
}

export interface TrunkedTalkgroup {
  id: string;
  release: ResourceRelease;
  identifier: string;
  name: string;
  system_name: string;
  talkgroup_id: number;
  mode: string;
  restrictions: string;
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
