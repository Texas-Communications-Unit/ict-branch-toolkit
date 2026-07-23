import * as maplibregl from "maplibre-gl";
import type {
  GeoJSONSource,
  MapMouseEvent,
  StyleSpecification,
} from "maplibre-gl";
import {
  type FormEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import {
  createManualRing,
  createRadioSite,
  createSiteAssignment,
  downloadSpatialExport,
  listPlans,
  listRadioSites,
  listSiteAssignments,
  parseCoordinate,
  searchAddress,
  updateRadioSite,
} from "./api";
import type {
  CoordinateParseResult,
  ICS205Plan,
  Incident,
  RadioSite,
  SiteAssignment,
} from "./types";

function brandColor(token: string, fallback: string) {
  if (typeof document === "undefined") return fallback;
  return (
    getComputedStyle(document.documentElement).getPropertyValue(token).trim() ||
    fallback
  );
}

function getBrandMapColors() {
  return {
    navy: brandColor("--tx-comu-navy", "#10233f"),
    blue: brandColor("--tx-comu-blue", "#1f5f99"),
    slate: brandColor("--tx-comu-slate", "#465466"),
    light: brandColor("--tx-comu-light", "#f4f7fb"),
    red: brandColor("--tx-comu-red", "#d72638"),
  };
}

function getOfflineStyle(): StyleSpecification {
  const colors = getBrandMapColors();
  return {
    version: 8,
    sources: {},
    layers: [
      {
        id: "background",
        type: "background",
        paint: { "background-color": colors.light },
      },
    ],
  };
}

function ringPolygon(site: RadioSite, radiusM: number) {
  const latitude = Number(site.latitude);
  const longitude = Number(site.longitude);
  const coordinates = Array.from({ length: 65 }, (_, index) => {
    const angle = (index * Math.PI * 2) / 64;
    const northM = Math.cos(angle) * radiusM;
    const eastM = Math.sin(angle) * radiusM;
    return [
      longitude +
        eastM /
          (111_320 * Math.max(Math.cos((latitude * Math.PI) / 180), 0.01)),
      latitude + northM / 111_320,
    ];
  });
  return coordinates;
}

export function MapShell({ incident }: { incident?: Incident }) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);
  const [sites, setSites] = useState<RadioSite[]>([]);
  const [plans, setPlans] = useState<ICS205Plan[]>([]);
  const [links, setLinks] = useState<SiteAssignment[]>([]);
  const [coordinateText, setCoordinateText] = useState("");
  const [parsed, setParsed] = useState<CoordinateParseResult>();
  const [message, setMessage] = useState("");
  const [addressResults, setAddressResults] = useState<
    { label: string; latitude: number; longitude: number; provider: string }[]
  >([]);
  const [addressSelection, setAddressSelection] = useState<{
    label: string;
    provider: string;
    retrievedAt: string;
  }>();

  const plan = plans.find((item) => item.incident === incident?.id);
  const revision =
    plan?.revisions.find((item) => item.status === "draft") ??
    plan?.revisions[0];
  const canEdit = incident?.permissions.includes("site.edit") ?? false;
  const canExport =
    (incident?.permissions.includes("site.export") ?? false) &&
    revision?.status === "approved";

  const refresh = useCallback(async () => {
    if (!incident) {
      setSites([]);
      setPlans([]);
      setLinks([]);
      return;
    }
    const [nextSites, nextPlans] = await Promise.all([
      listRadioSites(incident.id),
      listPlans(),
    ]);
    setSites(nextSites);
    setPlans(nextPlans);
    const incidentPlan = nextPlans.find(
      (item) => item.incident === incident.id,
    );
    const currentRevision =
      incidentPlan?.revisions.find((item) => item.status === "draft") ??
      incidentPlan?.revisions[0];
    setLinks(
      currentRevision ? await listSiteAssignments(currentRevision.id) : [],
    );
  }, [incident]);

  useEffect(() => {
    if (!incident) return;
    let active = true;
    void Promise.all([listRadioSites(incident.id), listPlans()])
      .then(async ([nextSites, nextPlans]) => {
        if (!active) return;
        setSites(nextSites);
        setPlans(nextPlans);
        const incidentPlan = nextPlans.find(
          (item) => item.incident === incident.id,
        );
        const currentRevision =
          incidentPlan?.revisions.find((item) => item.status === "draft") ??
          incidentPlan?.revisions[0];
        const nextLinks = currentRevision
          ? await listSiteAssignments(currentRevision.id)
          : [];
        if (active) setLinks(nextLinks);
      })
      .catch((error: Error) => {
        if (active) setMessage(error.message);
      });
    return () => {
      active = false;
    };
  }, [incident]);

  useEffect(() => {
    const handlePlanUpdate = () => {
      void refresh().catch((error: Error) => setMessage(error.message));
    };
    window.addEventListener("ict-plans-updated", handlePlanUpdate);
    return () =>
      window.removeEventListener("ict-plans-updated", handlePlanUpdate);
  }, [refresh]);

  useEffect(() => {
    if (!container.current) return;
    const configuredStyle = import.meta.env.VITE_MAP_STYLE_URL as
      string | undefined;
    const map = new maplibregl.Map({
      container: container.current,
      style: configuredStyle || getOfflineStyle(),
      center: [-99.4, 31.0],
      zoom: 4.6,
      attributionControl: false,
    });
    map.addControl(
      new maplibregl.NavigationControl({ showCompass: false }),
      "top-right",
    );
    const handleClick = (event: MapMouseEvent) => {
      const value = `${event.lngLat.lat.toFixed(6)}, ${event.lngLat.lng.toFixed(6)}`;
      setCoordinateText(value);
      setAddressSelection(undefined);
      setParsed({
        latitude: event.lngLat.lat,
        longitude: event.lngLat.lng,
        input_format: "decimal",
        formats: {
          decimal: value,
          ddm: "",
          dms: "",
          mgrs: "",
        },
      });
      setMessage("Map position selected. Name the site and save it.");
    };
    map.on("click", handleClick);
    mapRef.current = map;
    return () => {
      markersRef.current.forEach((marker) => marker.remove());
      markersRef.current = [];
      mapRef.current = null;
      map.remove();
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const render = () => {
      const colors = getBrandMapColors();
      const ringColors = {
        operational: colors.blue,
        fringe: colors.slate,
        coordination: colors.red,
      };
      markersRef.current.forEach((marker) => marker.remove());
      markersRef.current = sites.map((site) => {
        const marker = new maplibregl.Marker({
          color: colors.blue,
          draggable: canEdit,
        })
          .setLngLat([Number(site.longitude), Number(site.latitude)])
          .setPopup(
            new maplibregl.Popup({ offset: 22 }).setText(
              `${site.name}: ${site.coordinate_formats.decimal}`,
            ),
          )
          .addTo(map);
        if (canEdit) {
          marker.on("dragend", () => {
            const point = marker.getLngLat();
            void updateRadioSite(site.id, {
              latitude: point.lat.toFixed(6),
              longitude: point.lng.toFixed(6),
              entered_coordinate: `${point.lat.toFixed(6)}, ${point.lng.toFixed(6)}`,
              coordinate_format: "map",
            })
              .then(refresh)
              .catch((error: Error) => setMessage(error.message));
          });
        }
        return marker;
      });

      const ringFeatures = sites.flatMap((site) =>
        site.rings.map((ring) => ({
          type: "Feature" as const,
          properties: {
            site: site.name,
            ringType: ring.ring_type,
            color: ringColors[ring.ring_type],
          },
          geometry: {
            type: "Polygon" as const,
            coordinates: [ringPolygon(site, ring.radius_m)],
          },
        })),
      );
      const data = {
        type: "FeatureCollection" as const,
        features: ringFeatures,
      };
      const source = map.getSource("manual-rings") as GeoJSONSource | undefined;
      if (source) {
        source.setData(data);
      } else {
        map.addSource("manual-rings", { type: "geojson", data });
        map.addLayer({
          id: "manual-ring-fill",
          type: "fill",
          source: "manual-rings",
          paint: {
            "fill-color": ["get", "color"],
            "fill-opacity": 0.1,
          },
        });
        map.addLayer({
          id: "manual-ring-line",
          type: "line",
          source: "manual-rings",
          paint: {
            "line-color": ["get", "color"],
            "line-width": 2,
          },
        });
      }
      if (sites.length) {
        const bounds = new maplibregl.LngLatBounds();
        sites.forEach((site) =>
          bounds.extend([Number(site.longitude), Number(site.latitude)]),
        );
        map.fitBounds(bounds, { padding: 80, maxZoom: 12 });
      }
    };
    if (map.loaded()) render();
    else map.once("load", render);
  }, [canEdit, refresh, sites]);

  async function handleParse() {
    try {
      const result = await parseCoordinate(coordinateText);
      setParsed(result);
      setMessage(`Parsed as ${result.input_format.toUpperCase()}.`);
      mapRef.current?.flyTo({
        center: [result.longitude, result.latitude],
        zoom: 11,
      });
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Unable to parse coordinate.",
      );
    }
  }

  async function handleSite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!incident) return;
    const data = new FormData(event.currentTarget);
    try {
      await createRadioSite({
        incident: incident.id,
        name: String(data.get("siteName")),
        description: String(data.get("description")),
        coordinate_text: coordinateText,
        ...(addressSelection
          ? {
              address: addressSelection.label,
              source_identity: addressSelection.provider,
              source_retrieved_at: addressSelection.retrievedAt,
              coordinate_format: "address",
            }
          : {}),
      });
      event.currentTarget.reset();
      setCoordinateText("");
      setParsed(undefined);
      setAddressSelection(undefined);
      setMessage("Radio site saved.");
      await refresh();
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Unable to save site.",
      );
    }
  }

  async function handleAddress(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    try {
      const result = await searchAddress(String(data.get("address")));
      setAddressResults(result.results);
      setMessage(
        result.configured
          ? `${result.results.length} address result(s) returned by ${result.provider}.`
          : "No address provider is configured. Coordinate and map placement remain available.",
      );
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Address lookup failed.",
      );
    }
  }

  async function handleRing(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    try {
      await createManualRing({
        site: String(data.get("site")),
        ring_type: String(data.get("ringType")),
        radius_m: Number(data.get("radiusM")),
        label: String(data.get("ringLabel")),
      });
      event.currentTarget.reset();
      setMessage("Manual planning ring saved.");
      await refresh();
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Unable to save ring.",
      );
    }
  }

  async function handleCoordinateUpdate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    try {
      await updateRadioSite(String(data.get("site")), {
        coordinate_text: coordinateText,
        ...(addressSelection
          ? {
              address: addressSelection.label,
              source_identity: addressSelection.provider,
              source_retrieved_at: addressSelection.retrievedAt,
              coordinate_format: "address",
            }
          : {}),
      });
      setMessage("Radio site coordinates updated.");
      await refresh();
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Unable to update coordinates.",
      );
    }
  }

  async function handleLink(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    try {
      await createSiteAssignment(
        String(data.get("site")),
        String(data.get("assignment")),
      );
      setMessage("Site associated with the ICS-205 assignment.");
      await refresh();
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Unable to associate site.",
      );
    }
  }

  function exportRevision(format: "map" | "kml" | "geojson" | "csv") {
    if (!revision) return;
    void downloadSpatialExport(revision.id, format).catch((error: Error) =>
      setMessage(error.message),
    );
  }

  return (
    <section className="map-panel" aria-labelledby="map-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Spatial workspace</p>
          <h2 id="map-heading">Radio site planning</h2>
        </div>
        <span className="status-chip">P1.3 · WGS 84</span>
      </div>
      <div
        ref={container}
        className="map"
        data-testid="map"
        aria-label="Radio site planning map"
      />
      <p className="map-note">
        Click the map or enter decimal degrees, DDM, DMS, or USNG/MGRS. The
        neutral style works without a paid provider or network base map.
      </p>
      {!incident ? (
        <p className="empty">Select an incident to manage its radio sites.</p>
      ) : (
        <div className="site-workspace">
          {message && (
            <p role="status" className="site-message">
              {message}
            </p>
          )}
          {canEdit && (
            <form className="site-form" onSubmit={handleSite}>
              <h3>Place a radio site</h3>
              <label>
                Site name
                <input name="siteName" required />
              </label>
              <label>
                Coordinate
                <input
                  value={coordinateText}
                  onChange={(event) => {
                    setCoordinateText(event.target.value);
                    setAddressSelection(undefined);
                  }}
                  placeholder="33.214500, -97.133100"
                  required
                />
              </label>
              <button
                className="secondary-button"
                type="button"
                onClick={() => void handleParse()}
              >
                Parse and preview
              </button>
              <label>
                Description
                <input name="description" />
              </label>
              <button type="submit" disabled={!parsed}>
                Save radio site
              </button>
              {parsed && (
                <dl className="coordinate-preview">
                  <div>
                    <dt>Decimal</dt>
                    <dd>{parsed.formats.decimal}</dd>
                  </div>
                  {parsed.formats.mgrs && (
                    <div>
                      <dt>USNG/MGRS</dt>
                      <dd>{parsed.formats.mgrs}</dd>
                    </div>
                  )}
                </dl>
              )}
            </form>
          )}
          <div className="site-list">
            <h3>Incident sites</h3>
            {sites.length === 0 ? (
              <p className="empty">No sites have been placed.</p>
            ) : (
              sites.map((site) => (
                <article className="site-card" key={site.id}>
                  <strong>{site.name}</strong>
                  <span>{site.coordinate_formats.decimal}</span>
                  <small>{site.coordinate_formats.mgrs}</small>
                  <small>
                    {site.rings.length} ring(s) ·{" "}
                    {links.filter((link) => link.site === site.id).length}{" "}
                    assignment(s)
                  </small>
                </article>
              ))
            )}
            {canEdit && sites.length > 0 && (
              <form onSubmit={handleCoordinateUpdate}>
                <label>
                  Site to move using the parsed coordinate
                  <select name="site" required>
                    {sites.map((site) => (
                      <option key={site.id} value={site.id}>
                        {site.name}
                      </option>
                    ))}
                  </select>
                </label>
                <button type="submit" disabled={!parsed}>
                  Update selected site coordinates
                </button>
              </form>
            )}
          </div>
          {canEdit && sites.length > 0 && (
            <>
              <form className="site-form" onSubmit={handleRing}>
                <h3>Add a manual ring</h3>
                <label>
                  Site
                  <select name="site" required>
                    {sites.map((site) => (
                      <option key={site.id} value={site.id}>
                        {site.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Ring type
                  <select name="ringType">
                    <option value="operational">Operational</option>
                    <option value="fringe">Fringe / uncertain</option>
                    <option value="coordination">Coordination</option>
                  </select>
                </label>
                <label>
                  Radius in meters
                  <input name="radiusM" type="number" min="1" required />
                </label>
                <label>
                  Label
                  <input name="ringLabel" />
                </label>
                <button type="submit">Save ring</button>
              </form>
              {revision?.status === "draft" &&
                revision.assignments.length > 0 && (
                  <form className="site-form" onSubmit={handleLink}>
                    <h3>Associate site with assignment</h3>
                    <label>
                      Site
                      <select name="site" required>
                        {sites.map((site) => (
                          <option key={site.id} value={site.id}>
                            {site.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      ICS-205 assignment
                      <select name="assignment" required>
                        {revision.assignments.map((assignment) => (
                          <option key={assignment.id} value={assignment.id}>
                            {assignment.position}. {assignment.function} —{" "}
                            {assignment.channel_name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button type="submit">Associate site</button>
                  </form>
                )}
              <form className="site-form" onSubmit={handleAddress}>
                <h3>Optional address hook</h3>
                <label>
                  Address
                  <input name="address" required />
                </label>
                <button className="secondary-button" type="submit">
                  Search configured provider
                </button>
                {addressResults.map((result) => (
                  <button
                    className="address-result"
                    type="button"
                    key={`${result.provider}-${result.label}`}
                    onClick={() => {
                      const value = `${result.latitude.toFixed(6)}, ${result.longitude.toFixed(6)}`;
                      setCoordinateText(value);
                      setAddressSelection({
                        label: result.label,
                        provider: result.provider,
                        retrievedAt: new Date().toISOString(),
                      });
                      setParsed({
                        latitude: result.latitude,
                        longitude: result.longitude,
                        input_format: "decimal",
                        formats: {
                          decimal: value,
                          ddm: "",
                          dms: "",
                          mgrs: "",
                        },
                      });
                      mapRef.current?.flyTo({
                        center: [result.longitude, result.latitude],
                        zoom: 11,
                      });
                    }}
                  >
                    {result.label}
                  </button>
                ))}
              </form>
            </>
          )}
          {canExport && revision && (
            <div className="export-panel">
              <h3>Approved spatial exports</h3>
              <p>
                These files use the site snapshots frozen when revision{" "}
                {revision.number} was approved.
              </p>
              <div className="button-row">
                {(["map", "kml", "geojson", "csv"] as const).map((format) => (
                  <button
                    type="button"
                    key={format}
                    onClick={() => exportRevision(format)}
                  >
                    {format === "map" ? "SVG map" : format.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>
          )}
          <button
            type="button"
            className="text-button"
            onClick={() => void refresh()}
          >
            Refresh sites and plan status
          </button>
        </div>
      )}
    </section>
  );
}
