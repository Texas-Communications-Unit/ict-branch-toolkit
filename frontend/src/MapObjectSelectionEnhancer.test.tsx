import { act, fireEvent, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { MapObjectSelectionEnhancer } from "./MapObjectSelectionEnhancer";

async function flushEnhancer() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

function fixture() {
  document.body.innerHTML = `
    <div id="root">
      <button class="fcc-tower-marker" aria-label="Open FCC details for ASR 12345">Tower marker</button>
      <div class="fcc-tower-results">
        <button type="button" class="secondary-button">ASR 12345 — Synthetic County</button>
        <button type="button" class="secondary-button">ASR 67890 — Synthetic Utility</button>
      </div>
      <article class="fcc-tower-detail" aria-labelledby="fcc-tower-detail-heading">
        <h4 id="fcc-tower-detail-heading">ASR 12345</h4>
        <p>Synthetic FCC tower details</p>
      </article>
    </div>
  `;
}

describe("MapObjectSelectionEnhancer", () => {
  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("synchronizes pointer selection between map marker, result, and details", async () => {
    fixture();
    render(<MapObjectSelectionEnhancer />);
    await flushEnhancer();

    const marker = document.querySelector<HTMLElement>(".fcc-tower-marker")!;
    fireEvent.click(marker);
    await flushEnhancer();

    const result = Array.from(
      document.querySelectorAll<HTMLElement>(
        ".fcc-tower-results button.secondary-button",
      ),
    )[0];
    const detail = document.querySelector<HTMLElement>(".fcc-tower-detail")!;

    expect(marker.getAttribute("aria-pressed")).toBe("true");
    expect(result.getAttribute("aria-pressed")).toBe("true");
    expect(marker.textContent).toContain("Selected");
    expect(result.textContent).toContain("Selected");
    expect(detail.dataset.selectedObject).toBe("ASR 12345");
    expect(detail.textContent).toContain("Selected map object: ASR 12345");
  });

  it("supports keyboard selection and exposes a no-color-only selected cue", async () => {
    fixture();
    render(<MapObjectSelectionEnhancer />);
    await flushEnhancer();

    const result = Array.from(
      document.querySelectorAll<HTMLElement>(
        ".fcc-tower-results button.secondary-button",
      ),
    )[0];
    result.focus();
    fireEvent.keyDown(result, { key: "Enter" });
    await flushEnhancer();

    expect(result.getAttribute("aria-pressed")).toBe("true");
    expect(result.dataset.selectedObject).toBe("ASR 12345");
    expect(result.textContent).toContain("Selected");
    expect(document.activeElement).toBe(
      document.querySelector(".fcc-tower-detail"),
    );
  });

  it("closes selected details and restores focus to the originating control", async () => {
    fixture();
    render(<MapObjectSelectionEnhancer />);
    await flushEnhancer();

    const result = Array.from(
      document.querySelectorAll<HTMLElement>(
        ".fcc-tower-results button.secondary-button",
      ),
    )[0];
    result.focus();
    fireEvent.click(result);
    await flushEnhancer();

    const close = document.querySelector<HTMLElement>(
      "[data-map-selection-close]",
    )!;
    fireEvent.click(close);
    await flushEnhancer();

    const detail = document.querySelector<HTMLElement>(".fcc-tower-detail")!;
    expect(detail.hidden).toBe(true);
    expect(result.getAttribute("aria-pressed")).toBe("false");
    expect(document.activeElement).toBe(result);
  });

  it("supports Escape to close and restore focus", async () => {
    fixture();
    render(<MapObjectSelectionEnhancer />);
    await flushEnhancer();

    const marker = document.querySelector<HTMLElement>(".fcc-tower-marker")!;
    marker.focus();
    fireEvent.click(marker);
    await flushEnhancer();
    fireEvent.keyDown(document.activeElement ?? document.body, { key: "Escape" });
    await flushEnhancer();

    expect(
      document.querySelector<HTMLElement>(".fcc-tower-detail")!.hidden,
    ).toBe(true);
    expect(document.activeElement).toBe(marker);
  });
});
