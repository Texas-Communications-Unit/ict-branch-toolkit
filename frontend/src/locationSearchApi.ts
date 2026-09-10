export interface LocationSearchResult {
  label: string;
  latitude: number;
  longitude: number;
  crs: "EPSG:4326";
  provider: string;
  original_query: string;
  formats: Record<"decimal" | "ddm" | "dms" | "mgrs", string>;
}

export interface LocationSearchResponse {
  original_query: string;
  resolution_method: "local_coordinate" | "geocoder" | "what3words";
  external_lookup_performed: boolean;
  provider: string;
  configured: boolean;
  blocked_reason?: string;
  results: LocationSearchResult[];
}

function token() {
  return sessionStorage.getItem("ict-toolkit-token") ?? "";
}

export async function resolveLocation(
  query: string,
  externalLookupAllowed: boolean,
): Promise<LocationSearchResponse> {
  const response = await fetch("/api/locations/resolve/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token() ? { Authorization: `Token ${token()}` } : {}),
    },
    body: JSON.stringify({
      query,
      external_lookup_allowed: externalLookupAllowed,
    }),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail ?? "Location search failed.");
  }
  return data as LocationSearchResponse;
}
