import { expect, test } from "@playwright/test";

test("administrator signs in and sees the incident planning workspace", async ({
  page,
}, testInfo) => {
  await page.route("**/api/auth/token/", (route) =>
    route.fulfill({ json: { token: "synthetic-token" } }),
  );
  await page.route("**/api/incidents/", (route) =>
    route.fulfill({
      json: {
        count: 1,
        next: null,
        previous: null,
        results: [
          {
            id: "syn-1",
            name: "Synthetic Flood Exercise",
            incident_number: "SYN-001",
            status: "planning",
            operational_periods: [],
            archived_at: null,
            permissions: ["incident.view", "incident.archive", "period.create"],
          },
        ],
      },
    }),
  );
  await page.route("**/api/me/", (route) =>
    route.fulfill({
      json: {
        username: "admin",
        display_name: "Synthetic Administrator",
        role: "administrator",
        permissions: ["incident.create", "library.import"],
      },
    }),
  );
  await page.route("**/api/conventional-channels/", (route) =>
    route.fulfill({
      json: { count: 0, next: null, previous: null, results: [] },
    }),
  );
  await page.route("**/api/trunked-talkgroups/", (route) =>
    route.fulfill({
      json: { count: 0, next: null, previous: null, results: [] },
    }),
  );
  await page.route("**/api/channel-imports/", (route) =>
    route.fulfill({
      json: {
        valid: true,
        dry_run: true,
        approval_required: false,
        would_create: { releases: 1 },
        errors: [],
      },
    }),
  );
  await page.goto("/");
  await page.getByLabel("Username").fill("admin");
  await page.getByLabel("Password").fill("synthetic-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(
    page.getByRole("heading", { name: "Synthetic Flood Exercise" }),
  ).toBeVisible();
  await expect(page.getByLabel("Radio site planning map")).toBeVisible();
  await expect(page.getByText(/P1.1 Prototype/)).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Channel library" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Validate dry run" }).click();
  await expect(page.getByRole("status")).toContainText("Validation passed");
  await testInfo.attach("p1-1-workspace", {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  });
});
