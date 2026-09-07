import { useEffect } from "react";

import { getPointElevation, type PointElevation } from "./elevationApi";

const COORDINATE_PATTERN = /(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)/;

function coordinateFromText(text: string | null | undefined) {
  const match = text?.match(COORDINATE_PATTERN);
  if (!match) return null;
  const latitude = Number(match[1]);
  const longitude = Number(match[2]);
  if (
    !Number.isFinite(latitude) ||
    !Number.isFinite(longitude) ||
    latitude < -90 ||
    latitude > 90 ||
    longitude < -180 ||
    longitude > 180
  )
    return null;
  return { latitude, longitude };
}

function sourceLabel(result: PointElevation) {
  return result.provider === "usgs-3dep-epqs" ? "USGS 3DEP" : result.provider;
}

function metadataText(result: PointElevation) {
  const details = [sourceLabel(result)];
  if (result.source_acquisition_date) {
    details.push(`source acquisition ${result.source_acquisition_date}`);
  }
  if (result.retrieved_at) {
    details.push(`retrieved ${new Date(result.retrieved_at).toLocaleString()}`);
  }
  return details.join(" · ");
}

async function populateReadout(
  element: HTMLElement,
  latitude: number,
  longitude: number,
) {
  const coordinateKey = `${latitude.toFixed(7)},${longitude.toFixed(7)}`;
  if (element.dataset.elevationCoordinate === coordinateKey) return;
  element.dataset.elevationCoordinate = coordinateKey;
  element.dataset.elevationState = "loading";

  const value = element.querySelector<HTMLElement>("[data-elevation-value]");
  const metadata = element.querySelector<HTMLElement>(
    "[data-elevation-metadata]",
  );
  if (value) value.textContent = "Loading ground elevation…";
  if (metadata)
    metadata.textContent = "Using the approved public elevation source.";

  try {
    const result = await getPointElevation(latitude, longitude);
    if (element.dataset.elevationCoordinate !== coordinateKey) return;
    const feet = Number(result.elevation_ft);
    const meters = Number(result.elevation_m);
    if (value) {
      value.textContent = `Ground elevation: ${feet.toLocaleString(undefined, {
        maximumFractionDigits: 0,
      })} ft (${meters.toLocaleString(undefined, {
        minimumFractionDigits: 1,
        maximumFractionDigits: 1,
      })} m)`;
    }
    if (metadata) metadata.textContent = metadataText(result);
    element.dataset.elevationState = "complete";
  } catch (error) {
    if (element.dataset.elevationCoordinate !== coordinateKey) return;
    if (value) value.textContent = "Ground elevation unavailable";
    if (metadata) {
      metadata.textContent =
        error instanceof Error
          ? error.message
          : "The elevation service is temporarily unavailable.";
    }
    element.dataset.elevationState = "unavailable";
  }
}

function ensurePreviewReadout(preview: HTMLElement) {
  const decimal = Array.from(preview.querySelectorAll("dd"))
    .map((item) => coordinateFromText(item.textContent))
    .find(Boolean);
  if (!decimal) return;

  let wrapper = preview.querySelector<HTMLElement>(
    "[data-ground-elevation-preview]",
  );
  if (!wrapper) {
    wrapper = document.createElement("div");
    wrapper.dataset.groundElevationPreview = "true";
    const term = document.createElement("dt");
    term.textContent = "Ground elevation";
    const definition = document.createElement("dd");
    const value = document.createElement("span");
    value.dataset.elevationValue = "true";
    const metadata = document.createElement("small");
    metadata.dataset.elevationMetadata = "true";
    metadata.style.display = "block";
    definition.append(value, metadata);
    wrapper.append(term, definition);
    preview.append(wrapper);
  }
  void populateReadout(wrapper, decimal.latitude, decimal.longitude);
}

function ensureSiteReadout(card: HTMLElement) {
  const coordinate = coordinateFromText(card.querySelector("span")?.textContent);
  if (!coordinate) return;

  let wrapper = card.querySelector<HTMLElement>(
    "[data-ground-elevation-site]",
  );
  if (!wrapper) {
    wrapper = document.createElement("div");
    wrapper.dataset.groundElevationSite = "true";
    const value = document.createElement("small");
    value.dataset.elevationValue = "true";
    value.style.display = "block";
    const metadata = document.createElement("small");
    metadata.dataset.elevationMetadata = "true";
    metadata.style.display = "block";
    wrapper.append(value, metadata);
    card.append(wrapper);
  }
  void populateReadout(wrapper, coordinate.latitude, coordinate.longitude);
}

function scanForElevationTargets() {
  document
    .querySelectorAll<HTMLElement>("form.site-form .coordinate-preview")
    .forEach(ensurePreviewReadout);
  document
    .querySelectorAll<HTMLElement>(".site-list .site-card")
    .forEach(ensureSiteReadout);
}

export function ElevationEnhancer() {
  useEffect(() => {
    let scanQueued = false;
    const queueScan = () => {
      if (scanQueued) return;
      scanQueued = true;
      queueMicrotask(() => {
        scanQueued = false;
        scanForElevationTargets();
      });
    };

    scanForElevationTargets();
    const observer = new MutationObserver(queueScan);
    observer.observe(document.getElementById("root") ?? document.body, {
      childList: true,
      subtree: true,
      characterData: true,
    });
    return () => observer.disconnect();
  }, []);

  return null;
}
