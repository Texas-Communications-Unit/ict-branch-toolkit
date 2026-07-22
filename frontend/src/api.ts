import type {
  ConventionalChannel,
  CurrentUser,
  ImportResult,
  Incident,
  Paginated,
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
