import { useEffect } from "react";

import { enhanceFccMapUnits } from "./fccMapUnits";

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
