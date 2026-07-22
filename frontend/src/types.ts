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
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
