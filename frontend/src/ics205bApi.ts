const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const TOKEN_KEY = "ict-toolkit-token";
const TOKEN_EXPIRES_AT_KEY = "ict-toolkit-token-expires-at";
const AUTHENTICATION_EXPIRED_EVENT = "ict-toolkit-authentication-expired";

export interface ICS205BAssignment {
  id: string;
  form: string;
  position: number;
  assignment: string;
  it_resource_type: string;
  resource_name: string;
  usage_description: string;
  platform: string;
  developer: string;
  login_install: string;
  equipment_location: string;
  poc_information: string;
  remarks: string;
  created_at: string;
  updated_at: string;
}

export interface ICS205BForm {
  id: string;
  incident: string;
  incident_name: string;
  operational_period: string;
  operational_period_name: string;
  operational_period_starts_at: string;
  operational_period_ends_at: string;
  prepared_at: string | null;
  prepared_by_name: string;
  prepared_by_position: string;
  prepared_by_phone: string;
  prepared_by_signature: string;
  incident_location: string;
  state: string;
  county: string;
  city: string;
  assignments: ICS205BAssignment[];
  created_at: string;
  updated_at: string;
}

interface Paginated<T> {
  results: T[];
}

function tokenForRequest(): string | null {
  const token = sessionStorage.getItem(TOKEN_KEY);
  const expiresAt = sessionStorage.getItem(TOKEN_EXPIRES_AT_KEY);
  if (!token || !expiresAt || Date.now() >= Date.parse(expiresAt)) {
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(TOKEN_EXPIRES_AT_KEY);
    window.dispatchEvent(new Event(AUTHENTICATION_EXPIRED_EVENT));
    return null;
  }
  return token;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = tokenForRequest();
  if (!token) throw new Error("Your session expired. Sign in again.");
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Token ${token}`,
      ...options.headers,
    },
  });
  if (!response.ok) {
    if (response.status === 401) {
      sessionStorage.removeItem(TOKEN_KEY);
      sessionStorage.removeItem(TOKEN_EXPIRES_AT_KEY);
      window.dispatchEvent(new Event(AUTHENTICATION_EXPIRED_EVENT));
    }
    throw new Error(
      (await response.text()) ||
        `Request failed with status ${response.status}`,
    );
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function listICS205BForms(
  incident: string,
  operationalPeriod?: string,
): Promise<ICS205BForm[]> {
  const params = new URLSearchParams({ incident });
  if (operationalPeriod) params.set("operational_period", operationalPeriod);
  const page = await request<Paginated<ICS205BForm>>(
    `/api/ics205b-forms/?${params.toString()}`,
  );
  return page.results;
}

export function createICS205BForm(payload: {
  incident: string;
  operational_period: string;
  prepared_at?: string | null;
}): Promise<ICS205BForm> {
  return request<ICS205BForm>("/api/ics205b-forms/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateICS205BForm(
  formId: string,
  payload: Record<string, unknown>,
): Promise<ICS205BForm> {
  return request<ICS205BForm>(
    `/api/ics205b-forms/${encodeURIComponent(formId)}/`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
    },
  );
}

export function createICS205BAssignment(
  payload: Record<string, unknown>,
): Promise<ICS205BAssignment> {
  return request<ICS205BAssignment>("/api/ics205b-assignments/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateICS205BAssignment(
  assignmentId: string,
  payload: Record<string, unknown>,
): Promise<ICS205BAssignment> {
  return request<ICS205BAssignment>(
    `/api/ics205b-assignments/${encodeURIComponent(assignmentId)}/`,
    { method: "PATCH", body: JSON.stringify(payload) },
  );
}

export function deleteICS205BAssignment(assignmentId: string): Promise<void> {
  return request<void>(
    `/api/ics205b-assignments/${encodeURIComponent(assignmentId)}/`,
    { method: "DELETE" },
  );
}

export async function downloadICS205B(
  formId: string,
  format: "pdf" | "xlsx",
): Promise<void> {
  const token = tokenForRequest();
  if (!token) throw new Error("Your session expired. Sign in again.");
  const response = await fetch(
    `${API_BASE}/api/ics205b-forms/${encodeURIComponent(formId)}/${format}/`,
    { headers: { Authorization: `Token ${token}` } },
  );
  if (!response.ok)
    throw new Error((await response.text()) || "Export failed.");
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `ics-205b.${format}`;
  anchor.click();
  URL.revokeObjectURL(url);
}
