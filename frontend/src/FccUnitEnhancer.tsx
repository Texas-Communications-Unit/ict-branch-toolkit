import { useEffect } from "react";

import { formatMetersAsFeet } from "./unitFormatting";

const METRIC_HEIGHT_PATTERN = /^(-?\d+(?:\.\d+)?)\s*m$/i;

export function enhanceFccMapUnits(root: ParentNode = document) {
  root
    .querySelectorAll<HTMLElement>(".fcc-tower-detail .coordinate-preview > div")
    .forEach((row) => {
      const term = row.querySelector("dt")?.textContent?.trim();
      const value = row.querySelector("dd");
      if (term !== "Overall height" || !value) return;
      const current = value.textContent?.trim() ?? "";
      const match = current.match(METRIC_HEIGHT_PATTERN);
      if (!match) return;
      value.textContent = formatMetersAsFeet(match[1]);
    });
}

export function FccUnitEnhancer() {
  useEffect(() => {
    enhanceFccMapUnits();
    const observer = new MutationObserver(() => enhanceFccMapUnits());
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true,
    });
    return () => observer.disconnect();
  }, []);

  return null;
}
