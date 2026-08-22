import * as maplibregl from "maplibre-gl";
import type {
  GeoJSONSource,
  LngLatBoundsLike,
  MapMouseEvent,
  StyleSpecification,
} from "maplibre-gl";
import {
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  createManualRing,
  createRadioSite,
  createSiteAssignment,
  deleteSiteAssignment,
  downloadSpatialExport,
  getFccMapFeatures,
  getFccTowerDetails,
  listCoverageEstimates,
  listDirectionalCoverageAnalyses,
  listPlans,
  listRadioSites,
  listSiteAssignments,
  parseCoordinate,
  searchAddress,
  updateRadioSite,
} from "./api";
import { resolveMapProvider } from "./mapProvider";
import type {
  CoverageEstimate,
  DirectionalCoverageAnalysis,
  CoordinateParseResult,
  ICS205Plan,
  Incident,
  FccAntennaStructure,
  FccMapFeature,
  FccTowerDetail,
  RadioSite,
  SiteAssignment,
} from "./types";

const TEXAS_BOUNDS: LngLatBoundsLike = [
  [-106.65, 25.84],
  [-93.51, 36.5],
];

const TEXAS_FIT_OPTIONS = { padding: 36 };

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
  const fccMarkersRef = useRef<maplibregl.Marker[]>([]);
  const previewMarkerRef = useRef<maplibregl.Marker | null>(null);
  const configuredMap = useMemo(() => resolveMapProvider(import.meta.env), []);
  const [sites, setSites] = useState<RadioSite[]>([]);
  const [plans, setPlans] = useState<ICS205Plan[]>([]);
  const [links, setLinks] = useState<SiteAssignment[]>([]);
  const [coverageEstimates, setCoverageEstimates] = useState<
    CoverageEstimate[]
  >([]);
  const [directionalAnalyses, setDirectionalAnalyses] = useState<
    DirectionalCoverageAnalysis[]
  >([]);
  const [coordinateText, setCoordinateText] = useState("");
  const [parsed, setParsed] = useState<CoordinateParseResult>();
  const [message, setMessage] = useState("");
  const [mapStatus, setMapStatus] = useState("");
  const [fccLayerEnabled, setFccLayerEnabled] = useState(false);
  const [fccFeatures, setFccFeatures] = useState<FccMapFeature[]>([]);
  const [fccTowerCount, setFccTowerCount] = useState(0);
  const [fccSearch, setFccSearch] = useState("");
  const [fccStatusFilter, setFccStatusFilter] = useState("");
  const [fccStructureType, setFccStructureType] = useState("");
  const [selectedFccTower, setSelectedFccTower] = useState<FccTowerDetail>();
  const [fccStatus, setFccStatus] = useState(
    "FCC tower layer is off. Zoom to an area and enable it when needed.",
  );
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

  const previewCoordinate = useCallback(
    (latitude: number, longitude: number, moveMap = true) => {
      const map = mapRef.current;
      if (!map) return;
      const colors = getBrandMapColors();
      if (previewMarkerRef.current) {
        previewMarkerRef.current.setLngLat([longitude, latitude]);
      } else {
        previewMarkerRef.current = new maplibregl.Marker({
          color: colors.red,
        })
          .setLngLat([longitude, latitude])
          .addTo(map);
      }
      if (moveMap) {
        map.flyTo({
          center: [longitude, latitude],
          zoom: 11,
        });
      }
    },
    [],
  );

  const refresh = useCallback(async () => {
    if (!incident) {
      setSites([]);
      setPlans([]);
      setLinks([]);
      setCoverageEstimates([]);
      setDirectionalAnalyses([]);
      return;
    }
    const [
      nextSites,
      nextPlans,
      nextCoverageEstimates,
      nextDirectionalAnalyses,
    ] = await Promise.all([
      listRadioSites(incident.id),
      listPlans(),
      listCoverageEstimates(incident.id),
      listDirectionalCoverageAnalyses(incident.id),
    ]);
    setSites(nextSites);
    setPlans(nextPlans);
    setCoverageEstimates(nextCoverageEstimates);
    setDirectionalAnalyses(nextDirectionalAnalyses);
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
    void Promise.all([
      listRadioSites(incident.id),
      listPlans(),
      listCoverageEstimates(incident.id),
      listDirectionalCoverageAnalyses(incident.id),
    ])
      .then(
        async ([
          nextSites,
          nextPlans,
          nextCoverageEstimates,
          nextDirectionalAnalyses,
        ]) => {
          if (!active) return;
          setSites(nextSites);
          setPlans(nextPlans);
          setCoverageEstimates(nextCoverageEstimates);
          setDirectionalAnalyses(nextDirectionalAnalyses);
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
        },
      )
      .catch((error: Error) => {
        if (active) setMessage(error.message);
      });
    return () => {
      active = false;
    };
  }, [incident]);

  useEffect(() => {
    const handleCoverageUpdate = () => {
      void refresh().catch((error: Error) => setMessage(error.message));
    };
    window.addEventListener(
      "ict-coverage-estimates-updated",
      handleCoverageUpdate,
    );
    window.addEventListener(
      "ict-directional-analyses-updated",
      handleCoverageUpdate,
    );
    return () => {
      window.removeEventListener(
        "ict-coverage-estimates-updated",
        handleCoverageUpdate,
      );
      window.removeEventListener(
        "ict-directional-analyses-updated",
        handleCoverageUpdate,
      );
    };
  }, [refresh]);

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
    const map = new maplibregl.Map({
      container: container.current,
      style:
        configuredMap.mode === "external"
          ? configuredMap.style
          : getOfflineStyle(),
      bounds: TEXAS_BOUNDS,
      fitBoundsOptions: TEXAS_FIT_OPTIONS,
      attributionControl: false,
    });
    map.addControl(
      new maplibregl.NavigationControl({ showCompass: false }),
      "top-right",
    );
    if (configuredMap.mode === "external") {
      let waitingForExternalStyle = true;
      map.once("load", () => {
        waitingForExternalStyle = false;
      });
      map.once("error", () => {
        if (!waitingForExternalStyle) return;
        waitingForExternalStyle = false;
        map.setStyle(getOfflineStyle());
        setMapStatus(
          "The external basemap could not be loaded. The neutral map remains available.",
        );
      });
    }
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
      previewCoordinate(event.lngLat.lat, event.lngLat.lng, false);
      setMessage(
        "Map position selected and marked in red. Name the site and save it.",
      );
    };
    map.on("click", handleClick);
    mapRef.current = map;
    return () => {
      markersRef.current.forEach((marker) => marker.remove());
      markersRef.current = [];
      fccMarkersRef.current.forEach((marker) => marker.remove());
      fccMarkersRef.current = [];
      previewMarkerRef.current?.remove();
      previewMarkerRef.current = null;
      mapRef.current = null;
      map.remove();
    };
  }, [configuredMap, previewCoordinate]);

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
      const coverageFeatures = coverageEstimates.flatMap((estimate) => {
        if (
          estimate.calculation_state !== "complete" ||
          estimate.nominal_distance_m === null
        )
          return [];
        const site = sites.find((candidate) => candidate.id === estimate.site);
        if (!site) return [];
        return [
          {
            type: "Feature" as const,
            properties: {
              site: estimate.site_name,
              environment: estimate.environment,
              band: estimate.band,
              status: estimate.status,
              resultDigest: estimate.result_sha256,
            },
            geometry: {
              type: "Polygon" as const,
              coordinates: [ringPolygon(site, estimate.nominal_distance_m)],
            },
          },
        ];
      });
      const coverageData = {
        type: "FeatureCollection" as const,
        features: coverageFeatures,
      };
      const coverageSource = map.getSource("calculated-coverage-estimates") as
        GeoJSONSource | undefined;
      if (coverageSource) {
        coverageSource.setData(coverageData);
      } else {
        map.addSource("calculated-coverage-estimates", {
          type: "geojson",
          data: coverageData,
        });
        map.addLayer({
          id: "calculated-coverage-fill",
          type: "fill",
          source: "calculated-coverage-estimates",
          paint: {
            "fill-color": colors.blue,
            "fill-opacity": 0.06,
          },
        });
        map.addLayer({
          id: "calculated-coverage-line",
          type: "line",
          source: "calculated-coverage-estimates",
          paint: {
            "line-color": colors.blue,
            "line-width": 3,
            "line-dasharray": [2, 2],
          },
        });
      }
      const directionalFeatures = directionalAnalyses.flatMap((analysis) => {
        const site = sites.find((candidate) => candidate.id === analysis.site);
        if (!site) return [];
        return (
          [
            ["talk_out", analysis.talk_out_distance_m],
            ["talk_in", analysis.talk_in_distance_m],
            ["probable_two_way", analysis.probable_two_way_distance_m],
          ] as const
        ).flatMap(([path, radiusM]) =>
          radiusM === null
            ? []
            : [
                {
                  type: "Feature" as const,
                  properties: {
                    path,
                    site: analysis.site_name,
                    subscriber: analysis.subscriber_profile_name,
                    profileType: analysis.subscriber_profile_type,
                    limitingPath: analysis.limiting_path,
                    status: analysis.status,
                    resultDigest: analysis.result_sha256,
                  },
                  geometry: {
                    type: "Polygon" as const,
                    coordinates: [ringPolygon(site, radiusM)],
                  },
                },
              ],
        );
      });
      const directionalData = {
        type: "FeatureCollection" as const,
        features: directionalFeatures,
      };
      const directionalSource = map.getSource(
        "directional-coverage-analyses",
      ) as GeoJSONSource | undefined;
      if (directionalSource) {
        directionalSource.setData(directionalData);
      } else {
        map.addSource("directional-coverage-analyses", {
          type: "geojson",
          data: directionalData,
        });
        map.addLayer({
          id: "directional-coverage-fill",
          type: "fill",
          source: "directional-coverage-analyses",
          paint: {
            "fill-color": [
              "match",
              ["get", "path"],
              "talk_out",
              colors.blue,
              "talk_in",
              colors.red,
              colors.navy,
            ],
            "fill-opacity": [
              "match",
              ["get", "path"],
              "probable_two_way",
              0.12,
              0.035,
            ],
          },
        });
        map.addLayer({
          id: "directional-coverage-line",
          type: "line",
          source: "directional-coverage-analyses",
          paint: {
            "line-color": [
              "match",
              ["get", "path"],
              "talk_out",
              colors.blue,
              "talk_in",
              colors.red,
              colors.navy,
            ],
            "line-width": ["match", ["get", "path"], "probable_two_way", 4, 2],
            "line-dasharray": [
              "match",
              ["get", "path"],
              "probable_two_way",
              ["literal", [1, 0]],
              ["literal", [2, 2]],
            ],
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
  }, [canEdit, coverageEstimates, directionalAnalyses, refresh, sites]);

  const selectFccTower = useCallback(async (tower: FccAntennaStructure) => {
    try {
      setFccStatus(`Loading FCC details for ASR ${tower.registration_number}.`);
      const detail = await getFccTowerDetails(tower.id);
      setSelectedFccTower(detail);
      setFccStatus(
        `Loaded ASR ${tower.registration_number} with ${detail.license_count} associated license record(s).`,
      );
    } catch (error) {
      setFccStatus(
        error instanceof Error
          ? error.message
          : "Unable to load FCC tower details.",
      );
    }
  }, []);

  const refreshFccTowers = useCallback(
    async (
      filters = {
        search: fccSearch,
        status: fccStatusFilter,
        structureType: fccStructureType,
      },
    ) => {
      const map = mapRef.current;
      if (!map) return;
      const bounds = map.getBounds();
      setFccStatus("Loading FCC antenna structures in the current map view.");
      try {
        const result = await getFccMapFeatures({
          west: bounds.getWest().toString(),
          south: bounds.getSouth().toString(),
          east: bounds.getEast().toString(),
          north: bounds.getNorth().toString(),
          zoom: map.getZoom().toString(),
          search: filters.search,
          status: filters.status,
          structure_type: filters.structureType,
        });
        setFccFeatures(result.results);
        setFccTowerCount(result.count);
        setFccStatus(
          result.truncated
            ? `Showing the first ${result.feature_count} of ${result.count} FCC structures in this close view. Zoom in or filter to narrow the results.`
            : `Showing ${result.feature_count} map symbol${result.feature_count === 1 ? "" : "s"} representing ${result.count} FCC structure${result.count === 1 ? "" : "s"} in this view.`,
        );
      } catch (error) {
        setFccStatus(
          error instanceof Error
            ? error.message
            : "Unable to load the FCC tower layer.",
        );
      }
    },
    [fccSearch, fccStatusFilter, fccStructureType],
  );

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    fccMarkersRef.current.forEach((marker) => marker.remove());
    fccMarkersRef.current = [];
    if (!fccLayerEnabled) return;
    fccMarkersRef.current = fccFeatures.map((feature) => {
      if (feature.kind === "cluster") {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "fcc-tower-cluster";
        button.textContent = feature.count.toLocaleString();
        button.setAttribute(
          "aria-label",
          `Zoom to cluster of ${feature.count} FCC antenna structures`,
        );
        button.addEventListener("click", (event) => {
          event.stopPropagation();
          map.once("moveend", () => void refreshFccTowers());
          map.flyTo({
            center: [feature.longitude, feature.latitude],
            zoom: Math.min(map.getZoom() + 2, 18),
          });
        });
        return new maplibregl.Marker({ element: button })
          .setLngLat([feature.longitude, feature.latitude])
          .addTo(map);
      }
      const tower = feature.tower as FccAntennaStructure;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "fcc-tower-marker";
      button.setAttribute(
        "aria-label",
        `Open FCC details for ASR ${tower.registration_number}`,
      );
      button.title = `ASR ${tower.registration_number} — ${tower.owner_name || "owner not listed"}`;
      button.addEventListener("click", (event) => {
        event.stopPropagation();
        void selectFccTower(tower);
      });
      const popupContent = document.createElement("div");
      const heading = document.createElement("strong");
      heading.textContent = `ASR ${tower.registration_number}`;
      const summary = document.createElement("p");
      summary.textContent = `${tower.owner_name || "Owner not listed"} · ${tower.structure_type || "Structure type not listed"}`;
      popupContent.append(heading, summary);
      return new maplibregl.Marker({ element: button })
        .setLngLat([feature.longitude, feature.latitude])
        .setPopup(
          new maplibregl.Popup({ offset: 22 }).setDOMContent(popupContent),
        )
        .addTo(map);
    });
  }, [fccFeatures, fccLayerEnabled, refreshFccTowers, selectFccTower]);

  async function handleParse() {
    try {
      const result = await parseCoordinate(coordinateText);
      setParsed(result);
      setMessage(
        `Parsed as ${result.input_format.toUpperCase()} and marked in red.`,
      );
      previewCoordinate(result.latitude, result.longitude);
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Unable to parse coordinate.",
      );
    }
  }

  async function handleSite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!incident) return;
    const form = event.currentTarget;
    const data = new FormData(form);
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
      form.reset();
      setCoordinateText("");
      setParsed(undefined);
      setAddressSelection(undefined);
      previewMarkerRef.current?.remove();
      previewMarkerRef.current = null;
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
    const form = event.currentTarget;
    const data = new FormData(form);
    try {
      await createManualRing({
        site: String(data.get("site")),
        ring_type: String(data.get("ringType")),
        radius_m: Number(data.get("radiusM")),
        label: String(data.get("ringLabel")),
      });
      form.reset();
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

  async function handleUnlink(link: SiteAssignment) {
    if (
      !window.confirm(
        `Remove the link between ${link.site_name} and ${link.assignment_label}? The site and assignment will remain available.`,
      )
    ) {
      return;
    }
    try {
      await deleteSiteAssignment(link.id);
      setMessage(
        `Removed the link between ${link.site_name} and ${link.assignment_label}.`,
      );
      await refresh();
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Unable to remove the site association.",
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
        role="region"
        aria-label="Radio site planning map"
        aria-describedby="map-instructions"
      />
      <button
        type="button"
        className="secondary-button"
        onClick={() =>
          mapRef.current?.fitBounds(TEXAS_BOUNDS, TEXAS_FIT_OPTIONS)
        }
      >
        View all Texas
      </button>
      <section
        className="fcc-map-layer"
        aria-labelledby="fcc-map-layer-heading"
      >
        <div className="section-heading">
          <div>
            <p className="eyebrow">Authoritative public reference layer</p>
            <h3 id="fcc-map-layer-heading">FCC antenna structures</h3>
          </div>
          <span className="count">
            {fccLayerEnabled ? fccTowerCount : "Off"}
          </span>
        </div>
        <div className="button-row">
          <button
            type="button"
            className="secondary-button"
            aria-pressed={fccLayerEnabled}
            onClick={() => {
              const enabled = !fccLayerEnabled;
              setFccLayerEnabled(enabled);
              setSelectedFccTower(undefined);
              if (enabled) void refreshFccTowers();
              else {
                setFccFeatures([]);
                setFccTowerCount(0);
                setFccStatus("FCC tower layer is off.");
              }
            }}
          >
            {fccLayerEnabled ? "Turn off FCC towers" : "Turn on FCC towers"}
          </button>
          {fccLayerEnabled && (
            <button
              type="button"
              className="secondary-button"
              onClick={() => void refreshFccTowers()}
            >
              Refresh towers in current view
            </button>
          )}
        </div>
        {fccLayerEnabled && (
          <form
            className="fcc-map-filters"
            onSubmit={(event) => {
              event.preventDefault();
              setSelectedFccTower(undefined);
              void refreshFccTowers();
            }}
          >
            <label>
              Owner, ASR, FAA study, or type
              <input
                value={fccSearch}
                onChange={(event) => setFccSearch(event.target.value)}
              />
            </label>
            <label>
              FCC status code
              <input
                value={fccStatusFilter}
                onChange={(event) => setFccStatusFilter(event.target.value)}
                maxLength={8}
              />
            </label>
            <label>
              Structure type
              <input
                value={fccStructureType}
                onChange={(event) => setFccStructureType(event.target.value)}
                maxLength={40}
              />
            </label>
            <button type="submit" className="secondary-button">
              Apply tower filters
            </button>
            <button
              type="button"
              className="secondary-button"
              onClick={() => {
                setFccSearch("");
                setFccStatusFilter("");
                setFccStructureType("");
                setSelectedFccTower(undefined);
                void refreshFccTowers({
                  search: "",
                  status: "",
                  structureType: "",
                });
              }}
            >
              Clear filters
            </button>
          </form>
        )}
        <p
          role={fccLayerEnabled ? "status" : undefined}
          aria-live={fccLayerEnabled ? "polite" : undefined}
          className="site-message"
        >
          {fccStatus}
        </p>
        {fccLayerEnabled && fccFeatures.length > 0 && (
          <div className="fcc-tower-results">
            <h4>Map symbols in the current view</h4>
            <ul aria-label="FCC map symbols in the current map view">
              {fccFeatures.slice(0, 100).map((feature) => (
                <li key={feature.key}>
                  {feature.kind === "tower" && feature.tower ? (
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => void selectFccTower(feature.tower!)}
                    >
                      ASR {feature.tower.registration_number}
                      {feature.tower.owner_name
                        ? ` — ${feature.tower.owner_name}`
                        : ""}
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => {
                        const map = mapRef.current;
                        if (!map) return;
                        map.once("moveend", () => void refreshFccTowers());
                        map.flyTo({
                          center: [feature.longitude, feature.latitude],
                          zoom: Math.min(map.getZoom() + 2, 18),
                        });
                      }}
                    >
                      Zoom to {feature.count.toLocaleString()} clustered
                      structures
                    </button>
                  )}
                </li>
              ))}
            </ul>
            {fccFeatures.length > 100 && (
              <p className="empty">
                The accessible list shows the first 100 map symbols. Zoom in or
                apply filters to narrow the current view.
              </p>
            )}
          </div>
        )}
        {selectedFccTower && (
          <article
            className="fcc-tower-detail"
            aria-labelledby="fcc-tower-detail-heading"
          >
            <h4 id="fcc-tower-detail-heading">
              ASR {selectedFccTower.structure.registration_number}
            </h4>
            <p>
              <a
                href={selectedFccTower.structure.fcc_record_url}
                target="_blank"
                rel="noreferrer"
              >
                Open this structure in FCC ASR
              </a>
            </p>
            <dl className="coordinate-preview">
              <div>
                <dt>Owner</dt>
                <dd>{selectedFccTower.structure.owner_name || "Not listed"}</dd>
              </div>
              <div>
                <dt>Status</dt>
                <dd>
                  {selectedFccTower.structure.status_code || "Not listed"}
                </dd>
              </div>
              <div>
                <dt>Structure</dt>
                <dd>
                  {selectedFccTower.structure.structure_type || "Not listed"}
                </dd>
              </div>
              <div>
                <dt>Coordinates</dt>
                <dd>
                  {selectedFccTower.structure.latitude},{" "}
                  {selectedFccTower.structure.longitude}
                </dd>
              </div>
              <div>
                <dt>Overall height</dt>
                <dd>
                  {selectedFccTower.structure.overall_height_m
                    ? `${selectedFccTower.structure.overall_height_m} m`
                    : "Not listed"}
                </dd>
              </div>
              <div>
                <dt>FAA study</dt>
                <dd>
                  {selectedFccTower.structure.faa_study_number || "Not listed"}
                </dd>
              </div>
            </dl>
            <h5>Associated FCC licenses ({selectedFccTower.license_count})</h5>
            {selectedFccTower.licenses.length === 0 ? (
              <p className="empty">
                No imported ULS location references this ASR registration.
              </p>
            ) : (
              selectedFccTower.licenses.map((license) => (
                <section className="resource-card" key={license.id}>
                  <strong>
                    {license.call_sign} —{" "}
                    {license.licensee_name || "Licensee not listed"}
                  </strong>
                  <a
                    href={license.fcc_record_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Open {license.call_sign} in FCC ULS
                  </a>
                  <span>
                    Service {license.radio_service_code} · Status{" "}
                    {license.license_status}
                  </span>
                  {license.tower_locations.map((location) => (
                    <div key={location.location_number}>
                      <small>
                        Location {location.location_number} · {location.city}
                        {location.city && location.state ? ", " : ""}
                        {location.state}
                      </small>
                      {location.frequencies.length === 0 ? (
                        <p>No frequencies listed for this tower location.</p>
                      ) : (
                        <ul>
                          {location.frequencies.map((frequency, index) => {
                            const emissions = location.emissions
                              .filter(
                                (item) =>
                                  item.frequency_hz === frequency.frequency_hz,
                              )
                              .map((item) => item.emission_designator)
                              .filter(
                                (value, itemIndex, values) =>
                                  values.indexOf(value) === itemIndex,
                              );
                            return (
                              <li
                                key={`${frequency.frequency_hz}-${frequency.antenna_number}-${index}`}
                              >
                                {(frequency.frequency_hz / 1_000_000).toFixed(
                                  6,
                                )}{" "}
                                MHz
                                {frequency.station_class_code
                                  ? ` · ${frequency.station_class_code}`
                                  : ""}
                                {emissions.length
                                  ? ` · ${emissions.join(", ")}`
                                  : ""}
                              </li>
                            );
                          })}
                        </ul>
                      )}
                    </div>
                  ))}
                  <small>
                    {license.batch.dataset_label} · retrieved{" "}
                    {new Date(license.batch.retrieved_at).toLocaleDateString()}
                  </small>
                </section>
              ))
            )}
            {selectedFccTower.truncated && (
              <p className="empty">
                Only the first 100 associated licenses are shown.
              </p>
            )}
            <p className="map-note">{selectedFccTower.disclaimer}</p>
          </article>
        )}
      </section>
      {configuredMap.mode === "external" ? (
        <div className="map-provider" data-testid="map-provider">
          <p>
            Map data:{" "}
            <a href={configuredMap.metadata.attributionUrl}>
              {configuredMap.metadata.attributionText}
            </a>
            . Licensed under{" "}
            <a href={configuredMap.metadata.licenseUrl}>
              {configuredMap.metadata.licenseName}
            </a>
            . <a href={configuredMap.metadata.termsUrl}>Provider terms</a>
            {" · "}
            <a href={configuredMap.metadata.privacyUrl}>Provider privacy</a>
            {" · "}
            <a href={configuredMap.metadata.reportIssueUrl}>
              Report a map issue
            </a>
            {" · "}
            <a href={configuredMap.metadata.contactUrl}>Toolkit map support</a>
          </p>
          <p>
            Viewing this basemap sends the viewed geographic area to{" "}
            {configuredMap.metadata.name}. Do not display protected or
            confidential locations without an approved privacy and operational
            security determination.
          </p>
        </div>
      ) : (
        <p className="map-provider" data-testid="map-provider">
          Neutral offline map active. No map area or operational location is
          sent to an external map provider.
          {configuredMap.validationErrors.length > 0 &&
            " External basemap configuration is incomplete and was rejected."}
        </p>
      )}
      {mapStatus && (
        <p role="alert" className="site-message">
          {mapStatus}
        </p>
      )}
      <p className="map-note" id="map-instructions">
        Click the map or enter decimal degrees, DDM, DMS, or USNG/MGRS. Keyboard
        and screen-reader users can use the coordinate form and radio site list;
        map clicking and marker dragging are optional. Site coordinates are
        previewed with a red marker. Coordinates and manual rings remain
        available when an external basemap is disabled or unavailable.
        Calculated nominal estimates use a separate dashed layer and never
        replace operator-entered manual rings; the estimate table is the
        accessible non-map presentation.
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
              sites.map((site) => {
                const siteLinks = links.filter((link) => link.site === site.id);
                return (
                  <article className="site-card" key={site.id}>
                    <strong>{site.name}</strong>
                    <span>{site.coordinate_formats.decimal}</span>
                    <small>{site.coordinate_formats.mgrs}</small>
                    <small>
                      {site.rings.length} ring(s) · {siteLinks.length}{" "}
                      assignment(s)
                    </small>
                    {canEdit &&
                      revision?.status === "draft" &&
                      siteLinks.length > 0 && (
                        <ul
                          className="site-link-list"
                          aria-label={`Assignment links for ${site.name}`}
                        >
                          {siteLinks.map((link) => (
                            <li key={link.id}>
                              <span>{link.assignment_label}</span>
                              <button
                                type="button"
                                className="secondary-button"
                                aria-label={`Remove ${link.assignment_label} from ${site.name}`}
                                onClick={() => void handleUnlink(link)}
                              >
                                Remove link
                              </button>
                            </li>
                          ))}
                        </ul>
                      )}
                  </article>
                );
              })
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
                      previewCoordinate(result.latitude, result.longitude);
                      setMessage("Address result selected and marked in red.");
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
