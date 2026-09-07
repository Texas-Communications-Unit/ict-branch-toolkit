import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getPointElevation } from "./elevationApi";

describe("getPointElevation", () => {
  beforeEach(() => {
    sessionStorage.setItem("ict-toolkit-token", "test-token");
    sessionStorage.setItem(
      "ict-toolkit-token-expires-at",
      new Date(Date.now() + 60_000).toISOString(),
    );
  });

  afterEach(() => {
    sessionStorage.clear();
    vi.unstubAllGlobals();
  });

  it("requests authenticated elevation data", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        latitude: "33",
        longitude: "-97",
        elevation_m: "100.0",
        elevation_ft: "328.1",
        provider: "usgs-3dep-epqs",
        dataset_product: "USGS 3DEP",
        source_version: "EPQS API v1",
        vertical_crs: "NAVD 88",
        resolution_m: "10.000",
        source_resolution_degrees: null,
        source_raster_id: null,
        source_acquisition_date: "",
        retrieved_at: "2026-09-07T18:00:00Z",
        warnings: [],
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await getPointElevation(33, -97);

    expect(result.elevation_ft).toBe("328.1");
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/elevation-point/?latitude=33&longitude=-97"),
      { headers: { Authorization: "Token test-token" } },
    );
  });

  it("returns the safe server detail when elevation is unavailable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        json: async () => ({
          detail: "The elevation service is temporarily unavailable.",
        }),
      }),
    );

    await expect(getPointElevation(33, -97)).rejects.toThrow(
      "The elevation service is temporarily unavailable.",
    );
  });
});
