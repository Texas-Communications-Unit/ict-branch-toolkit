import { expect, test } from "@playwright/test";

test("FCC map selection stays synchronized and restores keyboard focus", async ({
  page,
}) => {
  await page.goto("/");

  await page.evaluate(() => {
    const fixture = document.createElement("section");
    fixture.dataset.testid = "synthetic-map-selection-fixture";
    fixture.innerHTML = `
      <button class="fcc-tower-marker" aria-label="Open FCC details for ASR 12345">Synthetic marker</button>
      <div class="fcc-tower-results">
        <button type="button" class="secondary-button">ASR 12345 — Synthetic County</button>
      </div>
      <article class="fcc-tower-detail" aria-labelledby="synthetic-fcc-heading">
        <h4 id="synthetic-fcc-heading">ASR 12345</h4>
        <p>Synthetic FCC reference detail</p>
      </article>
    `;
    document.body.append(fixture);
  });

  const marker = page.getByRole("button", {
    name: /open fcc details for asr 12345/i,
  });
  const result = page.getByRole("button", {
    name: /asr 12345.*synthetic county/i,
  });
  const detail = page.locator(".fcc-tower-detail");

  await marker.click();
  await expect(marker).toHaveAttribute("aria-pressed", "true");
  await expect(result).toHaveAttribute("aria-pressed", "true");
  await expect(marker).toContainText("Selected");
  await expect(result).toContainText("Selected");
  await expect(detail).toHaveAttribute("data-selected-object", "ASR 12345");
  await expect(detail).toContainText("Selected map object: ASR 12345");

  await result.focus();
  await result.press("Enter");
  await expect(detail).toBeFocused();

  await page.getByRole("button", { name: /close details for selected/i }).click();
  await expect(detail).toBeHidden();
  await expect(result).toBeFocused();
  await expect(result).toHaveAttribute("aria-pressed", "false");
});

test("Escape closes FCC details without relying on color for state", async ({ page }) => {
  await page.goto("/");

  await page.evaluate(() => {
    const fixture = document.createElement("section");
    fixture.dataset.testid = "synthetic-map-selection-escape-fixture";
    fixture.innerHTML = `
      <button class="fcc-tower-marker" aria-label="Open FCC details for ASR 67890">Synthetic marker</button>
      <div class="fcc-tower-results">
        <button type="button" class="secondary-button">ASR 67890 — Synthetic Utility</button>
      </div>
      <article class="fcc-tower-detail"><h4>ASR 67890</h4></article>
    `;
    document.body.append(fixture);
  });

  const marker = page.getByRole("button", {
    name: /open fcc details for asr 67890/i,
  });
  await marker.focus();
  await marker.press("Enter");

  await expect(marker).toHaveAttribute("data-selected-object", "ASR 67890");
  await expect(marker).toContainText("Selected");

  await page.keyboard.press("Escape");
  await expect(page.locator(".fcc-tower-detail")).toBeHidden();
  await expect(marker).toBeFocused();
});
