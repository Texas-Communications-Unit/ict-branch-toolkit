import { afterEach, describe, expect, it } from "vitest";

import { enhanceFccMapUnits } from "./FccUnitEnhancer";

afterEach(() => {
  document.body.innerHTML = "";
});

describe("FCC map companion units", () => {
  it("replaces a metric-only overall height with US-first companion text", () => {
    document.body.innerHTML = `
      <article class="fcc-tower-detail">
        <dl class="coordinate-preview">
          <div><dt>Overall height</dt><dd>100 m</dd></div>
        </dl>
      </article>
    `;

    enhanceFccMapUnits();

    expect(document.querySelector("dd")?.textContent).toBe("328 ft (100 m)");
  });

  it("is idempotent and leaves unavailable or unrelated values unchanged", () => {
    document.body.innerHTML = `
      <article class="fcc-tower-detail">
        <dl class="coordinate-preview">
          <div><dt>Overall height</dt><dd>Not listed</dd></div>
          <div><dt>Status</dt><dd>100 m</dd></div>
        </dl>
      </article>
    `;

    enhanceFccMapUnits();
    enhanceFccMapUnits();

    const values = Array.from(document.querySelectorAll("dd"), (item) => item.textContent);
    expect(values).toEqual(["Not listed", "100 m"]);
  });
});
