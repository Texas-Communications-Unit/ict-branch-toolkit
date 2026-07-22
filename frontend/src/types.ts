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
