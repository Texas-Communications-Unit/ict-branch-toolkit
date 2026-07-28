import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, type TestInfo } from "@playwright/test";

export const WCAG_22_AA_TAGS = [
  "wcag2a",
  "wcag2aa",
  "wcag21a",
  "wcag21aa",
  "wcag22aa",
] as const;

export async function expectNoAccessibilityViolations(
  page: Page,
  testInfo: TestInfo,
  checkpoint: string,
) {
  const results = await new AxeBuilder({ page })
    .withTags([...WCAG_22_AA_TAGS])
    .analyze();

  await testInfo.attach(`${checkpoint}-axe-results`, {
    body: JSON.stringify(
      {
        checkpoint,
        url: page.url(),
        testedTags: WCAG_22_AA_TAGS,
        violations: results.violations,
        incomplete: results.incomplete,
        passes: results.passes.map(({ id, impact, tags }) => ({
          id,
          impact,
          tags,
        })),
      },
      null,
      2,
    ),
    contentType: "application/json",
  });

  expect(
    results.violations,
    `axe found WCAG 2.2 Level A/AA violations at ${checkpoint}`,
  ).toEqual([]);
}

export async function expectDocumentReflow(page: Page) {
  const dimensions = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));

  expect(
    dimensions.scrollWidth,
    `document width ${dimensions.scrollWidth}px exceeds the ${dimensions.clientWidth}px viewport`,
  ).toBeLessThanOrEqual(dimensions.clientWidth);
}
