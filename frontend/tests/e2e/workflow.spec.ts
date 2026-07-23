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
              "site.view",
              "site.edit",
              "site.export",
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
  await page.route("**/api/radio-sites/?*", (route) =>
    route.fulfill({
      json: {
        count: 1,
        next: null,
        previous: null,
        results: [
          {
            id: "site-1",
            incident: "syn-1",
            name: "Synthetic Command Site",
            description: "Synthetic fixture",
            latitude: "33.214500",
            longitude: "-97.133100",
            entered_coordinate: "33.214500, -97.133100",
            coordinate_format: "decimal",
            coordinate_formats: {
              decimal: "33.214500, -97.133100",
              ddm: "33° 12.8700′ N, 97° 07.9860′ W",
              dms: "33° 12′ 52.20″ N, 97° 07′ 59.16″ W",
              mgrs: "14SQB7401876781",
            },
            address: "",
            source_identity: "",
            source_retrieved_at: null,
            rings: [
              {
                id: "ring-1",
                site: "site-1",
                ring_type: "operational",
                radius_m: 8000,
                label: "Synthetic operational ring",
              },
            ],
          },
        ],
      },
    }),
  );
  await page.route("**/api/site-assignments/?*", (route) =>
    route.fulfill({
      json: {
        count: 1,
        next: null,
        previous: null,
        results: [
          {
            id: "link-1",
            site: "site-1",
            site_name: "Synthetic Command Site",
            assignment: "row-1",
            assignment_label: "1. Command — SYN CALL",
            site_snapshot: {},
          },
        ],
      },
    }),
  );
  await page.route("**/api/coordinates/parse/", (route) =>
    route.fulfill({
      json: {
        latitude: 33.2145,
        longitude: -97.1331,
        input_format: "dms",
        formats: {
          decimal: "33.214500, -97.133100",
          ddm: "33° 12.8700′ N, 97° 07.9860′ W",
          dms: "33° 12′ 52.20″ N, 97° 07′ 59.16″ W",
          mgrs: "14SQB7401876781",
        },
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
    page.getByRole("button", { name: /^Synthetic Flood Exercise/ }),
  ).toBeVisible();
  await expect(
    page.getByRole("img", {
      name: "Texas Communications Unit (TX-COMU) logo",
    }),
  ).toBeVisible();
  await expect(page.getByText("ICT Toolkit")).toBeVisible();
  await expect(page.getByLabel("Radio site planning map")).toBeVisible();
  await expect(page.getByText(/P1.3 Prototype/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "ICS-205" })).toBeVisible();
  await expect(
    page.getByText("SYN CALL", { exact: true }).first(),
  ).toBeVisible();
  await expect(
    page.getByText("Synthetic Command Site", { exact: true }).first(),
  ).toBeVisible();
  await page
    .getByLabel("Coordinate", { exact: true })
    .fill("33° 12′ 52.20″ N, 97° 07′ 59.16″ W");
  await page.getByRole("button", { name: "Parse and preview" }).click();
  await expect(
    page.getByText("14SQB7401876781", { exact: true }).first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Approve and lock revision" }).click();
  await expect(
    page.getByRole("button", { name: "Download official PDF" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "SVG map" })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Channel library" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Validate dry run" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "Validation passed" }),
  ).toContainText("Validation passed");
  await expect(
    page.getByText(/Originally developed by the Texas Communications Unit/),
  ).toBeVisible();
  await expect(
    page.getByText(/TX-COMU names, logos, and identifying marks/),
  ).toBeVisible();
  const desktopScreenshot = testInfo.outputPath(
    "branded-workspace-desktop.png",
  );
  await page.screenshot({ path: desktopScreenshot, fullPage: true });
  await testInfo.attach("branded-workspace-desktop", {
    path: desktopScreenshot,
    contentType: "image/png",
  });

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("heading", { name: "ICT Branch Toolkit" }),
  ).toBeVisible();
  await expect(page.getByText(/P1.3 Prototype/)).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  const mobileScreenshot = testInfo.outputPath("branded-workspace-mobile.png");
  await page.screenshot({ path: mobileScreenshot, fullPage: true });
  await testInfo.attach("branded-workspace-mobile", {
    path: mobileScreenshot,
    contentType: "image/png",
  });
});
