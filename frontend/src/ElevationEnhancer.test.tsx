import { act, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ElevationEnhancer } from "./ElevationEnhancer";

function activeSession() {
  sessionStorage.setItem("ict-toolkit-token", "test-token");
  sessionStorage.setItem(
    "ict-toolkit-token-expires-at",
    new Date(Date.now() + 60_000).toISOString(),
  );
}

async function flushEnhancer() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe("ElevationEnhancer", () => {
  beforeEach(() => {
    activeSession();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          latitude: "33.06246",
          longitude: "-98.31144",
          elevation_m: "391.4",
          elevation_ft: "1284.1",
          provider: "usgs-3dep-epqs",
          dataset_product:
            "USGS 3D Elevation Program dynamic elevation service",
          source_version: "EPQS API v1",
          vertical_crs: "NAVD 88",
          resolution_m: "10.000",
          source_resolution_degrees: "0.0001",
          source_raster_id: "test-raster",
          source_acquisition_date: "2023-01-01",
          retrieved_at: "2026-09-07T18:00:00Z",
          warnings: [],
        }),
      }),
    );
  });

  afterEach(() => {
    document.body.innerHTML = "";
    sessionStorage.clear();
    vi.unstubAllGlobals();
  });

  it("adds feet and meters to a parsed coordinate preview", async () => {
    document.body.innerHTML = `
      <div id="root">
        <form class="site-form">
          <dl class="coordinate-preview">
            <div><dt>Decimal</dt><dd>33.062460, -98.311440</dd></div>
          </dl>
        </form>
      </div>
    `;

    render(<ElevationEnhancer />);
    await flushEnhancer();

    expect(document.body.textContent).toContain(
      "Ground elevation: 1,284 ft (391.4 m)",
    );
    expect(document.body.textContent).toContain("USGS 3DEP");
  });

  it("adds elevation to saved site cards without blocking on failure", async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      json: async () => ({
        detail: "The elevation service is temporarily unavailable.",
      }),
    } as Response);
    document.body.innerHTML = `
      <div id="root">
        <div class="site-list">
          <article class="site-card">
            <strong>Repeater Site</strong>
            <span>33.062460, -98.311440</span>
          </article>
        </div>
      </div>
    `;

    render(<ElevationEnhancer />);
    await flushEnhancer();

    expect(document.body.textContent).toContain("Ground elevation unavailable");
    expect(document.body.textContent).toContain(
      "The elevation service is temporarily unavailable.",
    );
    expect(document.body.textContent).toContain("Repeater Site");
  });
});
