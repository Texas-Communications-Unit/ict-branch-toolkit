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
          },
        ],
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
  await expect(page.getByText("P1.0 Prototype")).toBeVisible();
  await testInfo.attach("p1-0-workspace", {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  });
});
