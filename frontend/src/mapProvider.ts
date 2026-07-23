import type { StyleSpecification } from "maplibre-gl";

type MapEnvironment = Record<string, string | boolean | undefined>;

export interface MapProviderMetadata {
  id: string;
  name: string;
  attributionText: string;
  attributionUrl: string;
  licenseName: string;
  licenseUrl: string;
  termsUrl: string;
  privacyUrl: string;
  reportIssueUrl: string;
  contactUrl: string;
}

export type MapProviderResolution =
  | {
      mode: "offline";
      validationErrors: string[];
    }
  | {
      mode: "external";
      metadata: MapProviderMetadata;
      style: string | StyleSpecification;
      validationErrors: [];
    };

const METADATA_FIELDS = {
  VITE_MAP_PROVIDER_ID: "provider identifier",
  VITE_MAP_PROVIDER_NAME: "provider name",
  VITE_MAP_ATTRIBUTION_TEXT: "attribution text",
  VITE_MAP_ATTRIBUTION_URL: "attribution URL",
  VITE_MAP_LICENSE_NAME: "license name",
  VITE_MAP_LICENSE_URL: "license URL",
  VITE_MAP_TERMS_URL: "terms URL",
  VITE_MAP_PRIVACY_URL: "privacy URL",
  VITE_MAP_REPORT_ISSUE_URL: "map issue URL",
  VITE_MAP_CONTACT_URL: "operational contact URL",
} as const;

const URL_FIELDS = [
  "VITE_MAP_ATTRIBUTION_URL",
  "VITE_MAP_LICENSE_URL",
  "VITE_MAP_TERMS_URL",
  "VITE_MAP_PRIVACY_URL",
  "VITE_MAP_REPORT_ISSUE_URL",
  "VITE_MAP_CONTACT_URL",
] as const;

function value(environment: MapEnvironment, name: string) {
  const candidate = environment[name];
  return typeof candidate === "string" ? candidate.trim() : "";
}

function isHttpsUrl(candidate: string) {
  try {
    return new URL(candidate).protocol === "https:";
  } catch {
    return false;
  }
}

function rasterStyle(
  tileUrl: string,
  attributionText: string,
): StyleSpecification {
  return {
    version: 8,
    sources: {
      "configured-basemap": {
        type: "raster",
        tiles: [tileUrl],
        tileSize: 256,
        attribution: attributionText,
      },
    },
    layers: [
      {
        id: "configured-basemap",
        type: "raster",
        source: "configured-basemap",
      },
    ],
  };
}

export function resolveMapProvider(
  environment: MapEnvironment,
): MapProviderResolution {
  const styleUrl = value(environment, "VITE_MAP_STYLE_URL");
  const tileUrl = value(environment, "VITE_MAP_TILE_URL");
  if (!styleUrl && !tileUrl) {
    return { mode: "offline", validationErrors: [] };
  }

  const validationErrors: string[] = [];
  if (styleUrl && tileUrl) {
    validationErrors.push(
      "Configure either VITE_MAP_STYLE_URL or VITE_MAP_TILE_URL, not both.",
    );
  }
  const endpoint = styleUrl || tileUrl;
  if (!isHttpsUrl(endpoint)) {
    validationErrors.push("The configured map endpoint must use HTTPS.");
  }
  if (
    tileUrl &&
    (!tileUrl.includes("{z}") ||
      !tileUrl.includes("{x}") ||
      !tileUrl.includes("{y}"))
  ) {
    validationErrors.push(
      "The raster tile URL must contain {z}, {x}, and {y} placeholders.",
    );
  }

  for (const [field, label] of Object.entries(METADATA_FIELDS)) {
    if (!value(environment, field)) {
      validationErrors.push(`Missing ${label} (${field}).`);
    }
  }
  for (const field of URL_FIELDS) {
    const candidate = value(environment, field);
    if (candidate && !isHttpsUrl(candidate)) {
      validationErrors.push(`${field} must use HTTPS.`);
    }
  }

  const isPublicOsm =
    endpoint.includes("tile.openstreetmap.org") ||
    value(environment, "VITE_MAP_PROVIDER_ID") === "osm-standard";
  if (isPublicOsm) {
    if (
      tileUrl !== "https://tile.openstreetmap.org/{z}/{x}/{y}.png" ||
      styleUrl
    ) {
      validationErrors.push(
        "Public OSM testing must use the approved standard raster tile URL.",
      );
    }
    if (
      !value(environment, "VITE_MAP_ATTRIBUTION_TEXT").includes(
        "OpenStreetMap",
      ) ||
      value(environment, "VITE_MAP_ATTRIBUTION_URL") !==
        "https://www.openstreetmap.org/copyright"
    ) {
      validationErrors.push(
        "Public OSM testing requires visible OpenStreetMap attribution linked to its copyright page.",
      );
    }
  }

  if (validationErrors.length) {
    return { mode: "offline", validationErrors };
  }

  const metadata: MapProviderMetadata = {
    id: value(environment, "VITE_MAP_PROVIDER_ID"),
    name: value(environment, "VITE_MAP_PROVIDER_NAME"),
    attributionText: value(environment, "VITE_MAP_ATTRIBUTION_TEXT"),
    attributionUrl: value(environment, "VITE_MAP_ATTRIBUTION_URL"),
    licenseName: value(environment, "VITE_MAP_LICENSE_NAME"),
    licenseUrl: value(environment, "VITE_MAP_LICENSE_URL"),
    termsUrl: value(environment, "VITE_MAP_TERMS_URL"),
    privacyUrl: value(environment, "VITE_MAP_PRIVACY_URL"),
    reportIssueUrl: value(environment, "VITE_MAP_REPORT_ISSUE_URL"),
    contactUrl: value(environment, "VITE_MAP_CONTACT_URL"),
  };
  return {
    mode: "external",
    metadata,
    style: styleUrl ? styleUrl : rasterStyle(tileUrl, metadata.attributionText),
    validationErrors: [],
  };
}
