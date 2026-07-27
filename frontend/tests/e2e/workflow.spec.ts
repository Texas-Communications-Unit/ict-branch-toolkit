import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

async function expectNoAccessibilityViolations(
  page: import("@playwright/test").Page,
) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(results.violations).toEqual([]);
}

test("administrator signs in and sees the incident planning workspace", async ({
  page,
}, testInfo) => {
  let approved = false;
  let rfProfileCreated = false;
  let rfApproved = false;
  let rfSnapshotCreated = false;
  let rfInputs = {
    tx_frequency_hz: null as number | null,
    rx_frequency_hz: null as number | null,
    transmitter_power_w: null as string | null,
    effective_radiated_power_w: null as string | null,
    erp_source: "unknown",
    receiver_sensitivity_dbm: null as string | null,
    antenna_model: null as string | null,
    antenna_gain_db: null as string | null,
    antenna_gain_reference: "unknown",
    feed_line_type: null as string | null,
    feed_line_length_m: null as string | null,
    feed_line_loss_db: null as string | null,
    additional_system_loss_db: null as string | null,
    polarization: "unknown",
    frequency_band: "unknown",
    emission_designator: null as string | null,
    emission_bandwidth_hz: null as number | null,
    mounting_type: "unknown",
    antenna_center_agl_m: null as string | null,
    antenna_center_amsl_m: null as string | null,
    haat_m: null as string | null,
    input_basis: "unknown",
    notes: null as string | null,
  };
  const rfProfile = {
    id: "rf-profile-1",
    incident: "syn-1",
    name: "Synthetic Portable Assumption",
    profile_type: "portable",
    description: "Synthetic exercise values only",
    archived_at: null,
  };
  const rfVersion = () => ({
    id: "rf-version-1",
    profile: "rf-profile-1",
    number: 1,
    status: rfApproved ? "approved" : "draft",
    is_locked: rfApproved,
    approved_at: rfApproved ? "2026-07-27T22:00:00Z" : null,
    ...rfInputs,
    erp_calculation_path: rfApproved
      ? {
          formula: "transmitter_power_w + antenna_gain_db - system_losses_db",
          synthetic: true,
        }
      : null,
    input_snapshot: null,
    input_sha256: null,
  });
  await page.route("**/api/auth/token/", (route) =>
    route.fulfill({
      json: {
        token: "synthetic-token",
        expires_at: "2099-07-27T20:00:00Z",
      },
    }),
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
              "rf.view",
              "rf.edit",
              "rf.approve",
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
  await page.route("**/api/subscriber-profiles/?incident=*", (route) =>
    route.fulfill({
      json: {
        count: rfProfileCreated ? 1 : 0,
        next: null,
        previous: null,
        results: rfProfileCreated ? [rfProfile] : [],
      },
    }),
  );
  await page.route("**/api/subscriber-profiles/", async (route) => {
    expect(route.request().method()).toBe("POST");
    const payload = route.request().postDataJSON();
    expect(payload).toMatchObject({
      incident: "syn-1",
      name: "Synthetic Portable Assumption",
      profile_type: "portable",
      description: "Synthetic exercise values only",
    });
    expect(payload.initial_version.tx_frequency_hz).toBeNull();
    expect(payload.initial_version.erp_source).toBe("unknown");
    expect(payload.initial_version).not.toHaveProperty("erp_calculation_path");
    rfProfileCreated = true;
    return route.fulfill({ json: rfProfile });
  });
  await page.route("**/api/subscriber-profile-versions/?profile=*", (route) =>
    route.fulfill({
      json: {
        count: rfProfileCreated ? 1 : 0,
        next: null,
        previous: null,
        results: rfProfileCreated ? [rfVersion()] : [],
      },
    }),
  );
  await page.route(
    "**/api/subscriber-profile-versions/rf-version-1/",
    async (route) => {
      expect(route.request().method()).toBe("PATCH");
      rfInputs = route.request().postDataJSON();
      return route.fulfill({ json: rfVersion() });
    },
  );
  await page.route(
    "**/api/subscriber-profile-versions/rf-version-1/approve/",
    (route) => {
      rfApproved = true;
      return route.fulfill({ json: rfVersion() });
    },
  );
  await page.route(
    "**/api/subscriber-profile-versions/rf-version-1/create_snapshot/",
    async (route) => {
      expect(route.request().postDataJSON()).toEqual({
        label: "Synthetic RF baseline",
      });
      rfSnapshotCreated = true;
      return route.fulfill({
        json: {
          id: "rf-snapshot-1",
          incident: "syn-1",
          profile_version: "rf-version-1",
          label: "Synthetic RF baseline",
          input_snapshot: rfVersion(),
          input_sha256: "b".repeat(64),
          created_at: "2026-07-27T22:05:00Z",
        },
      });
    },
  );
  await page.route("**/api/rf-analysis-input-snapshots/?incident=*", (route) =>
    route.fulfill({
      json: {
        count: rfSnapshotCreated ? 1 : 0,
        next: null,
        previous: null,
        results: rfSnapshotCreated
          ? [
              {
                id: "rf-snapshot-1",
                incident: "syn-1",
                profile_version: "rf-version-1",
                label: "Synthetic RF baseline",
                input_snapshot: rfVersion(),
                input_sha256: "b".repeat(64),
                created_at: "2026-07-27T22:05:00Z",
              },
            ]
          : [],
      },
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
  await expectNoAccessibilityViolations(page);
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Username")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Password")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Sign in" })).toBeFocused();
  await page.getByLabel("Username").fill("admin");
  await page.getByLabel("Password").fill("synthetic-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(
    page.getByRole("button", { name: /^Synthetic Flood Exercise/ }),
  ).toBeVisible();
  const workspaceLogo = page.getByRole("img", {
    name: "Texas Communications Unit (TX-COMU) logo",
  });
  await expect(workspaceLogo).toBeVisible();
  await expect(page.locator("picture.brand-mark source")).toHaveAttribute(
    "srcset",
    "/brand/tx-comu-logo-transparent.svg",
  );
  await expect(page.getByText("ICT Toolkit")).toBeVisible();
  const planningMap = page.getByRole("region", {
    name: "Radio site planning map",
  });
  await expect(planningMap).toBeVisible();
  await expect(planningMap).toHaveAccessibleDescription(
    /Keyboard and screen-reader users can use the coordinate form/,
  );
  await page.evaluate(() => (document.activeElement as HTMLElement)?.blur());
  await page.keyboard.press("Tab");
  const skipLink = page.getByRole("link", {
    name: "Skip to planning workspace",
  });
  await expect(skipLink).toBeFocused();
  await skipLink.press("Enter");
  await expect(page.locator("#main-content")).toBeFocused();
  await expect(page.getByText(/P2.1 Prototype/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "ICS-205" })).toBeVisible();
  await expect(
    page.getByText("SYN CALL", { exact: true }).first(),
  ).toBeVisible();
  await expect(
    page.getByText("Synthetic Command Site", { exact: true }).first(),
  ).toBeVisible();
  const rfWorkspace = page.getByRole("region", {
    name: "Subscriber RF profiles",
  });
  await expect(rfWorkspace).toBeVisible();
  await expect(
    rfWorkspace.getByText(/synthetic or explicitly approved data only/i),
  ).toBeVisible();
  await rfWorkspace.getByText("Create subscriber profile").click();
  const createProfile = rfWorkspace.locator("details.rf-create-profile");
  await createProfile
    .getByLabel("Profile name")
    .fill("Synthetic Portable Assumption");
  await createProfile.getByLabel("Profile type").selectOption("portable");
  await createProfile
    .getByLabel("Description")
    .fill("Synthetic exercise values only");
  await createProfile
    .getByRole("button", { name: "Create profile and draft" })
    .click();
  await expect(
    rfWorkspace.getByRole("option", {
      name: "Synthetic Portable Assumption · Portable",
    }),
  ).toBeAttached();
  await rfWorkspace.getByLabel("Transmit frequency (Hz)").fill("155000000");
  await rfWorkspace.getByLabel("Transmitter power (W)").fill("5.2500");
  await rfWorkspace
    .getByLabel("Effective radiated power (ERP) (W)")
    .fill("7.1000");
  await rfWorkspace.getByLabel("ERP source").selectOption("entered");
  await rfWorkspace.getByLabel("Antenna gain (dB)").fill("2.15");
  await rfWorkspace.getByLabel("Feed-line loss (dB)").fill("0.30");
  await rfWorkspace.getByLabel("Antenna center AGL (m)").fill("12.50");
  await rfWorkspace.getByLabel("Emission bandwidth (Hz)").fill("11200");
  await rfWorkspace
    .getByLabel("Input basis")
    .selectOption("modeled_assumption");
  await rfWorkspace
    .getByLabel("Notes")
    .fill("Synthetic modeled assumptions for browser verification");
  await rfWorkspace.getByRole("button", { name: "Save RF draft" }).click();
  await expect.poll(() => rfInputs.transmitter_power_w).toBe("5.2500");
  expect(rfInputs.tx_frequency_hz).toBe(155000000);
  expect(rfInputs.rx_frequency_hz).toBeNull();
  page.once("dialog", (dialog) => dialog.accept());
  await rfWorkspace
    .getByRole("button", { name: "Approve and lock RF version" })
    .click();
  await expect(
    rfWorkspace.getByText("Server calculation path and immutable provenance"),
  ).toBeVisible();
  await rfWorkspace.getByLabel("Snapshot label").fill("Synthetic RF baseline");
  await rfWorkspace
    .getByRole("button", { name: "Create immutable snapshot" })
    .click();
  await expect(
    rfWorkspace.getByText("Synthetic RF baseline", { exact: true }).last(),
  ).toBeVisible();
  await expect(rfWorkspace.getByText("b".repeat(64))).toBeVisible();
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
  await expectNoAccessibilityViolations(page);
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
  await expect(page.getByText(/P2.1 Prototype/)).toBeVisible();
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
