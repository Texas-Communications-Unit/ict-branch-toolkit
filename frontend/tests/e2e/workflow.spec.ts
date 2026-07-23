import { expect, test } from "@playwright/test";

test("administrator signs in and sees the incident planning workspace", async ({
  page,
}, testInfo) => {
  let approved = false;
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
            operational_periods: [
              {
                id: "period-1",
                name: "Operational Period 1",
                starts_at: "2026-07-23T08:00:00Z",
                ends_at: "2026-07-23T20:00:00Z",
              },
            ],
            archived_at: null,
            permissions: [
              "incident.view",
              "incident.archive",
              "period.create",
              "plan.view",
              "plan.edit",
              "plan.approve",
              "plan.export",
            ],
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
  await page.route("**/api/ics205-plans/", (route) =>
    route.fulfill({
      json: {
        count: 1,
        next: null,
        previous: null,
        results: [
          {
            id: "plan-1",
            incident: "syn-1",
            operational_period: "period-1",
            title: "Incident Radio Communications Plan",
            revisions: [
              {
                id: "rev-1",
                plan: "plan-1",
                number: 1,
                status: approved ? "approved" : "draft",
                is_locked: approved,
                prepared_by_name: "Synthetic Planner",
                prepared_by_position: "COML",
                approved_at: approved ? "2026-07-23T20:00:00Z" : null,
                relationships: [],
                assignments: [
                  {
                    id: "row-1",
                    revision: "rev-1",
                    position: 1,
                    function: "Command",
                    channel_name: "SYN CALL",
                    assignment: "Incident command",
                    rx_frequency_hz: 155001000,
                    tx_frequency_hz: 155001000,
                    rx_squelch: "CSQ",
                    tx_squelch: "CSQ",
                    mode: "Analog FM",
                    remarks: "Synthetic only",
                    structured_note: "",
                    contact_name: "",
                    site_address: "",
                    phone_numbers: "",
                    contact_24_hour: "",
                    resource_snapshot: { type: "incident" },
                  },
                ],
              },
            ],
          },
        ],
      },
    }),
  );
  await page.route("**/api/plan-revisions/rev-1/approve/", (route) => {
    approved = true;
    return route.fulfill({ json: {} });
  });
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
  await expect(page.getByText(/P1.2 Prototype/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "ICS-205" })).toBeVisible();
  await expect(page.getByText("SYN CALL")).toBeVisible();
  await page.getByRole("button", { name: "Approve and lock revision" }).click();
  await expect(
    page.getByRole("button", { name: "Download official PDF" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Channel library" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Validate dry run" }).click();
  await expect(page.getByRole("status")).toContainText("Validation passed");
  await testInfo.attach("p1-2-workspace", {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  });
});
