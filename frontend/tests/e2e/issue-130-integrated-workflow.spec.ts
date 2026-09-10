import { expect, test } from "@playwright/test";

test("Issue 130 integrated workflow preserves search, selection, units, provenance, and NIFOG semantics", async ({
  page,
}) => {
  await page.route("**/api/locations/resolve/", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        original_query: "33.214500, -97.133100",
        resolution_method: "local_coordinate",
        external_lookup_performed: false,
        provider: "local-coordinate-parser",
        configured: true,
        results: [
          {
            label: "Synthetic command site",
            latitude: 33.2145,
            longitude: -97.1331,
            crs: "EPSG:4326",
            provider: "local-coordinate-parser",
            original_query: "33.214500, -97.133100",
            formats: {
              decimal: "33.214500, -97.133100",
              ddm: "33° 12.8700′ N, 97° 07.9860′ W",
              dms: "33° 12′ 52.20″ N, 97° 07′ 59.16″ W",
              mgrs: "14S synthetic",
            },
          },
        ],
      }),
    });
  });

  await page.goto("/");

  await page.evaluate(() => {
    const panel = document.createElement("section");
    panel.className = "map-panel";
    panel.innerHTML = `
      <h2 id="map-heading">Synthetic map</h2>
      <label>Coordinate
        <input placeholder="33.214500, -97.133100" />
      </label>
      <button type="button">Parse and preview</button>
      <button class="incident-site-marker" type="button" aria-label="Incident-created radio site Synthetic ICP">Incident site</button>
      <button class="fcc-tower-marker" type="button" aria-label="Open FCC details for ASR 12345">FCC tower</button>
      <div class="fcc-tower-results">
        <button type="button" class="secondary-button">ASR 12345 — Synthetic County</button>
      </div>
      <article class="fcc-tower-detail" aria-labelledby="synthetic-fcc-heading">
        <h4 id="synthetic-fcc-heading">ASR 12345</h4>
        <dl class="coordinate-preview">
          <div><dt>Overall height</dt><dd>100 m</dd></div>
        </dl>
        <p>FCC source: Synthetic ASR/ULS reference fixture</p>
        <div class="nifog-frequency-match" aria-label="NIFOG exact-frequency match for 159.472500 megahertz">
          <strong>Interoperability reference match</strong>
          <span>159.472500 MHz · SYN-A (RX/TX) · SYN-B (RX)</span>
          <span>Source: Synthetic NIFOG · release SYN-2</span>
          <small>Reference match only. This does not authorize transmission, coordination, licensing applicability, or emission compatibility.</small>
        </div>
      </article>
    `;
    panel.querySelector("button:not([class])")?.addEventListener("click", () => {
      panel.dataset.previewed = "true";
    });
    document.body.append(panel);
  });

  const search = page.getByRole("heading", { name: "Map location search" });
  await expect(search).toBeVisible();

  await page.getByLabel("Location").fill("33.214500, -97.133100");
  await page.getByRole("button", { name: "Resolve location" }).click();
  await expect(page.getByRole("status")).toContainText("1 normalized WGS 84 result available");

  await page.getByRole("button", { name: /synthetic command site/i }).click();
  await expect(page.locator('input[placeholder="33.214500, -97.133100"]')).toHaveValue(
    "33.214500, -97.133100",
  );
  await expect(page.locator("section.map-panel")).toHaveAttribute("data-previewed", "true");

  const incidentSite = page.getByRole("button", {
    name: /incident-created radio site synthetic icp/i,
  });
  const fccMarker = page.getByRole("button", {
    name: /open fcc details for asr 12345/i,
  });
  const fccResult = page.getByRole("button", {
    name: /asr 12345.*synthetic county/i,
  });
  const detail = page.locator(".fcc-tower-detail");

  await expect(incidentSite).not.toHaveAttribute("aria-pressed", "true");
  await fccMarker.focus();
  await fccMarker.press("Enter");
  await expect(fccMarker).toHaveAttribute("aria-pressed", "true");
  await expect(fccResult).toHaveAttribute("aria-pressed", "true");
  await expect(fccMarker).toContainText("Selected");
  await expect(detail).toBeFocused();
  await expect(incidentSite).not.toHaveAttribute("data-selected-object", "ASR 12345");

  await expect(detail.getByText("328 ft (100 m)")).toBeVisible();
  await expect(detail).toContainText("FCC source: Synthetic ASR/ULS reference fixture");

  const nifogMatch = detail.locator(".nifog-frequency-match");
  await expect(nifogMatch).toContainText("Interoperability reference match");
  await expect(nifogMatch).toContainText("SYN-A (RX/TX)");
  await expect(nifogMatch).toContainText("SYN-B (RX)");
  await expect(nifogMatch).toContainText("release SYN-2");
  await expect(nifogMatch).toContainText("does not authorize transmission");

  await page.keyboard.press("Escape");
  await expect(detail).toBeHidden();
  await expect(fccMarker).toBeFocused();
});

test("Issue 130 local coordinate planning remains available without optional provider lookup", async ({
  page,
}) => {
  await page.route("**/api/locations/resolve/", async (route) => {
    const request = route.request();
    const payload = request.postDataJSON() as {
      query: string;
      external_lookup_allowed: boolean;
    };
    expect(payload.external_lookup_allowed).toBe(false);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        original_query: payload.query,
        resolution_method: "local_coordinate",
        external_lookup_performed: false,
        provider: "local-coordinate-parser",
        configured: false,
        results: [
          {
            label: "Local coordinate",
            latitude: 33.2145,
            longitude: -97.1331,
            crs: "EPSG:4326",
            provider: "local-coordinate-parser",
            original_query: payload.query,
            formats: {
              decimal: "33.214500, -97.133100",
              ddm: "33° 12.8700′ N, 97° 07.9860′ W",
              dms: "33° 12′ 52.20″ N, 97° 07′ 59.16″ W",
              mgrs: "14S synthetic",
            },
          },
        ],
      }),
    });
  });

  await page.goto("/");
  await page.evaluate(() => {
    const panel = document.createElement("section");
    panel.className = "map-panel";
    panel.innerHTML = `
      <h2 id="map-heading">Synthetic map</h2>
      <input placeholder="33.214500, -97.133100" />
      <button type="button">Parse and preview</button>
    `;
    document.body.append(panel);
  });

  await page.getByLabel("Location").fill("33.214500, -97.133100");
  await expect(page.getByLabel(/Allow this query/)).not.toBeChecked();
  await page.getByRole("button", { name: "Resolve location" }).click();
  await expect(page.getByRole("button", { name: /local coordinate/i })).toBeVisible();
});
