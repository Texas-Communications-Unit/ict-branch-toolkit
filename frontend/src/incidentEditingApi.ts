import { ApiError } from "./api";
import type { Incident, OperationalPeriod } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const TOKEN_KEY = "ict-toolkit-token";
const TOKEN_EXPIRES_AT_KEY = "ict-toolkit-token-expires-at";

function activeToken(): string {
  const token = sessionStorage.getItem(TOKEN_KEY);
  const expiresAt = sessionStorage.getItem(TOKEN_EXPIRES_AT_KEY);
  if (
    !token ||
    !expiresAt ||
    !Number.isFinite(Date.parse(expiresAt)) ||
    Date.now() >= Date.parse(expiresAt)
  ) {
    throw new Error("Your session expired. Sign in again.");
  }
  return token;
}

async function patch<T>(path: string, payload: Record<string, string>): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "PATCH",
    headers: {
      Authorization: `Token ${activeToken()}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const text = await response.text();
    let data: unknown = text;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      // Keep the server's plain-text response.
    }
    throw new ApiError(text || `Request failed with status ${response.status}`, response.status, data);
  }
  return (await response.json()) as T;
}

export function updateIncidentName(id: string, name: string): Promise<Incident> {
  return patch<Incident>(`/api/incidents/${encodeURIComponent(id)}/`, { name });
}

export function updateOperationalPeriod(
  id: string,
  payload: { name: string; starts_at: string; ends_at: string },
): Promise<OperationalPeriod> {
  return patch<OperationalPeriod>(
    `/api/operational-periods/${encodeURIComponent(id)}/`,
    payload,
  );
}
