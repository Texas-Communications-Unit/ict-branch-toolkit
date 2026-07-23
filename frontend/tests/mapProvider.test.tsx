import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import { MapShell } from "../src/MapShell";
import { resolveMapProvider } from "../src/mapProvider";

const osmEnvironment = {
  VITE_MAP_TILE_URL: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
  VITE_MAP_PROVIDER_ID: "osm-standard",
  VITE_MAP_PROVIDER_NAME: "OpenStreetMap standard tiles",
  VITE_MAP_ATTRIBUTION_TEXT: "© OpenStreetMap contributors",
  VITE_MAP_ATTRIBUTION_URL: "https://www.openstreetmap.org/copyright",
  VITE_MAP_LICENSE_NAME: "Open Database License 1.0",
  VITE_MAP_LICENSE_URL: "https://opendatacommons.org/licenses/odbl/1-0/",
  VITE_MAP_TERMS_URL: "https://operations.osmfoundation.org/policies/tiles/",
  VITE_MAP_PRIVACY_URL: "https://osmfoundation.org/wiki/Privacy_Policy",
  VITE_MAP_REPORT_ISSUE_URL: "https://www.openstreetmap.org/fixthemap",
  VITE_MAP_CONTACT_URL:
    "https://github.com/Texas-Communications-Unit/ict-branch-toolkit/issues",
};

describe("resolveMapProvider", () => {
  test("keeps the neutral map when no external provider is configured", () => {
    expect(resolveMapProvider({})).toEqual({
      mode: "offline",
      validationErrors: [],
    });
  });

  test("builds the policy-compliant public OSM raster style", () => {
    const result = resolveMapProvider(osmEnvironment);

    expect(result.mode).toBe("external");
    if (result.mode === "external") {
      expect(result.metadata.attributionText).toBe(
        "© OpenStreetMap contributors",
      );
      expect(result.style).toMatchObject({
        sources: {
          "configured-basemap": {
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
          },
        },
      });
    }
  });

  test("fails closed when provider governance metadata is incomplete", () => {
    const result = resolveMapProvider({
      VITE_MAP_TILE_URL: "https://tiles.example.test/{z}/{x}/{y}.png",
      VITE_MAP_PROVIDER_NAME: "Incomplete provider",
    });

    expect(result.mode).toBe("offline");
    expect(result.validationErrors).toContain(
      "Missing provider identifier (VITE_MAP_PROVIDER_ID).",
    );
    expect(result.validationErrors).toContain(
      "Missing attribution text (VITE_MAP_ATTRIBUTION_TEXT).",
    );
  });

  test("rejects an incorrect public OSM endpoint", () => {
    const result = resolveMapProvider({
      ...osmEnvironment,
      VITE_MAP_TILE_URL: "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
    });

    expect(result.mode).toBe("offline");
    expect(result.validationErrors).toContain(
      "Public OSM testing must use the approved standard raster tile URL.",
    );
  });

  test("rejects insecure metadata and map endpoints", () => {
    const result = resolveMapProvider({
      ...osmEnvironment,
      VITE_MAP_TILE_URL: "http://tiles.example.test/{z}/{x}/{y}.png",
      VITE_MAP_PROVIDER_ID: "example",
      VITE_MAP_ATTRIBUTION_URL: "http://example.test/copyright",
    });

    expect(result.mode).toBe("offline");
    expect(result.validationErrors).toContain(
      "The configured map endpoint must use HTTPS.",
    );
    expect(result.validationErrors).toContain(
      "VITE_MAP_ATTRIBUTION_URL must use HTTPS.",
    );
  });
});

describe("MapShell provider disclosure", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  test("shows linked attribution and privacy disclosure for an external map", () => {
    for (const [name, setting] of Object.entries(osmEnvironment)) {
      vi.stubEnv(name, setting);
    }

    render(<MapShell />);

    expect(
      screen.getByRole("link", { name: "© OpenStreetMap contributors" }),
    ).toHaveAttribute("href", "https://www.openstreetmap.org/copyright");
    expect(screen.getByTestId("map-provider")).toHaveTextContent(
      "Viewing this basemap sends the viewed geographic area",
    );
    expect(
      screen.getByRole("link", { name: "Report a map issue" }),
    ).toHaveAttribute("href", "https://www.openstreetmap.org/fixthemap");
  });
});
