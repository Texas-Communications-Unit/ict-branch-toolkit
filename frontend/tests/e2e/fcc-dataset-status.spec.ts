import { expect, test } from "@playwright/test";

import {
  expectDocumentReflow,
  expectNoAccessibilityViolations,
} from "./accessibility";

test("FCC status supports error recovery, keyboard provenance, and narrow reflow", async ({
  page,
}, testInfo) => {
  let failed = true;
  await page.addInitScript(() => {
    sessionStorage.setItem("ict-toolkit-token", "synthetic-status-token");
    sessionStorage.setItem(
      "ict-toolkit-token-expires-at",
      "2099-01-01T00:00:00Z",
    );
  });
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/me/") {
      return route.fulfill({
        json: {
          username: "synthetic-reader",
          display_name: "Synthetic Reader",
          role: "read_only",
          permissions: ["library.view"],
        },
      });
    }
    if (path === "/api/fcc-dataset-status/") {
      if (failed)
        return route.fulfill({
          status: 503,
          json: { detail: "Synthetic unavailable" },
        });
      return route.fulfill({
        json: {
          generated_at: "2026-11-04T12:00:00Z",
          datasets: ["asr", "uls_private", "uls_commercial"].map((dataset) => ({
            dataset,
            label:
              dataset === "asr"
                ? "Antenna Structure Registration"
                : dataset === "uls_private"
                  ? "ULS private land mobile"
                  : "ULS commercial land mobile",
            status: dataset === "asr" ? "available" : "not_imported",
            retrieved_at: "2026-10-27T12:00:00Z",
            imported_at: "2026-10-27T12:00:00Z",
            retrieved_age_days: 8,
            timestamp_warning: false,
            last_checked_at: null,
            record_counts: { antenna_structures: 12000 },
            archive_name: "r_tower.zip",
            source_url:
              "https://data.fcc.gov/download/pub/uls/complete/r_tower.zip",
            content_sha256: "a".repeat(64),
            parser_version: "synthetic-v1",
          })),
        },
      });
    }
    if (path === "/api/external-identity/status/") {
      return route.fulfill({
        json: {
          enabled: false,
          configured: false,
          provider: "local",
          login_url: null,
        },
      });
    }
    return route.fulfill({
      json: { count: 0, next: null, previous: null, results: [] },
    });
  });
  await page.goto("/");
  await page.getByRole("tab", { name: "FCC Reference", exact: true }).click();
  await page
    .getByText("FCC dataset status and provenance", { exact: true })
    .press("Enter");
  await expect(page.getByRole("alert")).toContainText(
    "FCC search is still available",
  );
  await expect(
    page.getByRole("button", { name: "Search FCC records" }),
  ).toBeEnabled();
  await expectNoAccessibilityViolations(
    page,
    testInfo,
    "fcc-dataset-status-error",
  );
  failed = false;
  await page
    .getByRole("button", { name: "Retry dataset status" })
    .press("Enter");
  await expect(page.getByText("Archive retrieved 8 days ago.")).toBeVisible();
  await page.getByText("Import provenance", { exact: true }).press("Enter");
  await expect(
    page.getByRole("link", { name: "Official FCC complete archive" }),
  ).toBeVisible();
  await expectNoAccessibilityViolations(
    page,
    testInfo,
    "fcc-dataset-status-provenance",
  );
  await page.setViewportSize({ width: 320, height: 900 });
  await expectDocumentReflow(page);
  await expectNoAccessibilityViolations(
    page,
    testInfo,
    "fcc-dataset-status-narrow",
  );
  const screenshot = testInfo.outputPath("fcc-dataset-status-320.png");
  await page.screenshot({ path: screenshot, fullPage: true });
  await testInfo.attach("fcc-dataset-status-320", {
    path: screenshot,
    contentType: "image/png",
  });
});
