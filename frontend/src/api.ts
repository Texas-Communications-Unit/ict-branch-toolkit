import type {
  ConventionalChannel,
  CurrentUser,
  ImportResult,
  Incident,
  ICS205Plan,
  Paginated,
  PlanAssignment,
  PlanRelationship,
  PlanRevision,
  RevisionComparison,
  TrunkedTalkgroup,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = sessionStorage.getItem("ict-toolkit-token");
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Token ${token}` } : {}),
      ...options.headers,
    },
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with status ${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function login(username: string, password: string): Promise<void> {
  const result = await request<{ token: string }>("/api/auth/token/", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  sessionStorage.setItem("ict-toolkit-token", result.token);
}

export async function listIncidents(): Promise<Incident[]> {
  const result = await request<Paginated<Incident>>("/api/incidents/");
  return result.results;
}

export function getCurrentUser(): Promise<CurrentUser> {
  return request<CurrentUser>("/api/me/");
}

export async function listConventionalChannels(): Promise<
  ConventionalChannel[]
> {
  const result = await request<Paginated<ConventionalChannel>>(
    "/api/conventional-channels/",
  );
  return result.results;
}

export async function listTrunkedTalkgroups(): Promise<TrunkedTalkgroup[]> {
  const result = await request<Paginated<TrunkedTalkgroup>>(
    "/api/trunked-talkgroups/",
  );
  return result.results;
}

export function importChannelLibrary(payload: object): Promise<ImportResult> {
  return request<ImportResult>("/api/channel-imports/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function createIncident(
  name: string,
  incidentNumber: string,
): Promise<Incident> {
  return request<Incident>("/api/incidents/", {
    method: "POST",
    body: JSON.stringify({ name, incident_number: incidentNumber }),
  });
}

export async function createOperationalPeriod(
  incident: string,
  name: string,
  startsAt: string,
  endsAt: string,
): Promise<void> {
  await request("/api/operational-periods/", {
    method: "POST",
    body: JSON.stringify({
      incident,
      name,
      starts_at: new Date(startsAt).toISOString(),
      ends_at: new Date(endsAt).toISOString(),
    }),
  });
}

export async function archiveIncident(incident: string): Promise<void> {
  await request(`/api/incidents/${incident}/archive/`, { method: "POST" });
}

export async function listPlans(): Promise<ICS205Plan[]> {
  const result = await request<Paginated<ICS205Plan>>("/api/ics205-plans/");
  return result.results;
}

export function createPlan(
  incident: string,
  operationalPeriod: string,
): Promise<ICS205Plan> {
  return request<ICS205Plan>("/api/ics205-plans/", {
    method: "POST",
    body: JSON.stringify({
      incident,
      operational_period: operationalPeriod,
      title: "Incident Radio Communications Plan",
    }),
  });
}

export function createPlanAssignment(
  payload: Record<string, unknown>,
): Promise<PlanAssignment> {
  return request<PlanAssignment>("/api/plan-assignments/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deletePlanAssignment(id: string): Promise<void> {
  return request<void>(`/api/plan-assignments/${id}/`, { method: "DELETE" });
}

export function reorderPlanAssignments(
  revision: string,
  assignmentIds: string[],
): Promise<PlanAssignment[]> {
  return request<PlanAssignment[]>("/api/plan-assignments/reorder/", {
    method: "POST",
    body: JSON.stringify({ revision, assignment_ids: assignmentIds }),
  });
}

export function createPlanRelationship(
  payload: Record<string, unknown>,
): Promise<PlanRelationship> {
  return request<PlanRelationship>("/api/plan-relationships/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function approvePlanRevision(id: string): Promise<PlanRevision> {
  return request<PlanRevision>(`/api/plan-revisions/${id}/approve/`, {
    method: "POST",
  });
}

export function copyPlanRevision(id: string): Promise<PlanRevision> {
  return request<PlanRevision>(`/api/plan-revisions/${id}/copy/`, {
    method: "POST",
  });
}

export function comparePlanRevisions(
  id: string,
  other: string,
): Promise<RevisionComparison> {
  return request<RevisionComparison>(
    `/api/plan-revisions/${id}/compare/?other=${encodeURIComponent(other)}`,
  );
}

export async function downloadPlanPdf(id: string): Promise<void> {
  const token = sessionStorage.getItem("ict-toolkit-token");
  const response = await fetch(`${API_BASE}/api/plan-revisions/${id}/pdf/`, {
    headers: token ? { Authorization: `Token ${token}` } : {},
  });
  if (!response.ok) throw new Error(await response.text());
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "ics-205.pdf";
  anchor.click();
  URL.revokeObjectURL(url);
}
