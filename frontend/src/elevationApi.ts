export interface PointElevation {
  latitude: string;
  longitude: string;
  elevation_m: string;
  elevation_ft: string;
  provider: string;
  dataset_product: string;
  source_version: string;
  vertical_crs: string;
  resolution_m: string | null;
  source_resolution_degrees: string | null;
  source_raster_id: string | null;
  source_acquisition_date: string;
  retrieved_at: string;
  warnings: string[];
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const TOKEN_KEY = "ict-toolkit-token";
const TOKEN_EXPIRES_AT_KEY = "ict-toolkit-token-expires-at";

function activeToken(): string | null {
  const token = sessionStorage.getItem(TOKEN_KEY);
  const expiresAt = sessionStorage.getItem(TOKEN_EXPIRES_AT_KEY);
  if (!token || !expiresAt) return null;
  const expiresAtMs = Date.parse(expiresAt);
  if (!Number.isFinite(expiresAtMs) || Date.now() >= expiresAtMs) return null;
  return token;
}

export async function getPointElevation(
  latitude: number,
  longitude: number,
): Promise<PointElevation> {
  const token = activeToken();
  if (!token) throw new Error("Elevation lookup requires an active session.");

  const query = new URLSearchParams({
    latitude: latitude.toString(),
    longitude: longitude.toString(),
  });
  const response = await fetch(`${API_BASE}/api/elevation-point/?${query}`, {
    headers: { Authorization: `Token ${token}` },
  });
  if (!response.ok) {
    let message = "Ground elevation is unavailable.";
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) message = payload.detail;
    } catch {
      // Keep the operator-safe fallback message.
    }
    throw new Error(message);
  }
  return (await response.json()) as PointElevation;
}
