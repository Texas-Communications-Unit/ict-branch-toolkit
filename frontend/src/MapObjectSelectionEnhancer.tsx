import { useEffect } from "react";

const SELECTABLE_SELECTOR =
  ".fcc-tower-marker, .fcc-tower-results button.secondary-button";
const DETAIL_SELECTOR = ".fcc-tower-detail";
const BADGE_CLASS = "map-object-selection-badge";
const SELECTED_CLASS = "is-map-object-selected";

function extractAsr(element: Element | null): string | null {
  if (!element) return null;
  const text = [
    element.getAttribute("aria-label"),
    element.getAttribute("title"),
    element.textContent,
  ]
    .filter(Boolean)
    .join(" ");
  return text.match(/\bASR\s+(\d+)\b/i)?.[1] ?? null;
}

function selectionBadge(button: HTMLElement) {
  let badge = button.querySelector<HTMLElement>(`.${BADGE_CLASS}`);
  if (!badge) {
    badge = document.createElement("span");
    badge.className = BADGE_CLASS;
    badge.textContent = "Selected";
    button.append(badge);
  }
  return badge;
}

function removeSelectionBadge(button: HTMLElement) {
  button.querySelector(`.${BADGE_CLASS}`)?.remove();
}

function findDetail(asr: string): HTMLElement | null {
  return Array.from(document.querySelectorAll<HTMLElement>(DETAIL_SELECTOR)).find(
    (detail) => !detail.hidden && extractAsr(detail) === asr,
  ) ?? null;
}

function findSelectable(target: EventTarget | null): HTMLElement | null {
  return target instanceof Element
    ? target.closest<HTMLElement>(SELECTABLE_SELECTOR)
    : null;
}

export function MapObjectSelectionEnhancer() {
  useEffect(() => {
    let selectedAsr: string | null = null;
    let lastTrigger: HTMLElement | null = null;
    let pendingDetailFocus = false;
    let applying = false;

    function clearSelection({ restoreFocus = true } = {}) {
      const trigger = lastTrigger;
      selectedAsr = null;
      pendingDetailFocus = false;
      document
        .querySelectorAll<HTMLElement>(SELECTABLE_SELECTOR)
        .forEach((button) => {
          button.classList.remove(SELECTED_CLASS);
          button.setAttribute("aria-pressed", "false");
          button.removeAttribute("data-selected-object");
          removeSelectionBadge(button);
        });
      document.querySelectorAll<HTMLElement>(DETAIL_SELECTOR).forEach((detail) => {
        detail.classList.remove(SELECTED_CLASS);
        detail.removeAttribute("data-selected-object");
        detail.querySelector("[data-map-selection-summary]")?.remove();
        detail.querySelector("[data-map-selection-close]")?.remove();
        detail.hidden = true;
      });
      if (restoreFocus && trigger?.isConnected) {
        queueMicrotask(() => trigger.focus());
      }
    }

    function applySelection() {
      if (applying) return;
      applying = true;
      try {
        document
          .querySelectorAll<HTMLElement>(SELECTABLE_SELECTOR)
          .forEach((button) => {
            const isSelected =
              selectedAsr !== null && extractAsr(button) === selectedAsr;
            button.classList.toggle(SELECTED_CLASS, isSelected);
            button.setAttribute("aria-pressed", isSelected ? "true" : "false");
            if (isSelected) {
              button.dataset.selectedObject = `ASR ${selectedAsr}`;
              selectionBadge(button);
            } else {
              button.removeAttribute("data-selected-object");
              removeSelectionBadge(button);
            }
          });

        if (!selectedAsr) return;
        const detail = findDetail(selectedAsr);
        if (!detail) return;

        detail.hidden = false;
        detail.classList.add(SELECTED_CLASS);
        detail.dataset.selectedObject = `ASR ${selectedAsr}`;
        detail.tabIndex = -1;

        if (!detail.querySelector("[data-map-selection-summary]")) {
          const summary = document.createElement("p");
          summary.dataset.mapSelectionSummary = "true";
          summary.className = "map-object-selection-summary";
          summary.setAttribute("role", "status");
          summary.textContent = `Selected map object: ASR ${selectedAsr}. Map marker, result list, and details are synchronized.`;
          detail.prepend(summary);
        }

        if (!detail.querySelector("[data-map-selection-close]")) {
          const close = document.createElement("button");
          close.type = "button";
          close.dataset.mapSelectionClose = "true";
          close.className = "secondary-button map-object-selection-close";
          close.textContent = "Close selected object details";
          close.setAttribute(
            "aria-label",
            `Close details for selected FCC antenna structure ASR ${selectedAsr}`,
          );
          close.addEventListener("click", () => clearSelection());
          detail.prepend(close);
        }

        if (pendingDetailFocus) {
          pendingDetailFocus = false;
          queueMicrotask(() => {
            if (detail.isConnected && !detail.hidden) detail.focus();
          });
        }
      } finally {
        applying = false;
      }
    }

    function select(button: HTMLElement) {
      const asr = extractAsr(button);
      if (!asr) return;
      selectedAsr = asr;
      lastTrigger = button;
      pendingDetailFocus = true;
      applySelection();
    }

    function syncFromVisibleDetail() {
      const detail = Array.from(
        document.querySelectorAll<HTMLElement>(DETAIL_SELECTOR),
      ).find((candidate) => !candidate.hidden);
      const detailAsr = extractAsr(detail ?? null);
      if (detailAsr && detailAsr !== selectedAsr) {
        selectedAsr = detailAsr;
        pendingDetailFocus = false;
      }
      applySelection();
    }

    function handleClick(event: MouseEvent) {
      const button = findSelectable(event.target);
      if (button) select(button);
    }

    function handleKeydown(event: KeyboardEvent) {
      if (event.key === "Escape" && selectedAsr) {
        event.preventDefault();
        clearSelection();
        return;
      }
      if (event.key !== "Enter" && event.key !== " ") return;
      const button = findSelectable(event.target);
      if (button) select(button);
    }

    const observer = new MutationObserver(() => syncFromVisibleDetail());
    observer.observe(document.body, { childList: true, subtree: true });
    document.addEventListener("click", handleClick, true);
    document.addEventListener("keydown", handleKeydown, true);
    syncFromVisibleDetail();

    return () => {
      observer.disconnect();
      document.removeEventListener("click", handleClick, true);
      document.removeEventListener("keydown", handleKeydown, true);
    };
  }, []);

  return null;
}
