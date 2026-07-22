import * as maplibregl from "maplibre-gl";
import type { StyleSpecification } from "maplibre-gl";
import { useEffect, useRef } from "react";

const offlineStyle: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [
    {
      id: "background",
      type: "background",
      paint: { "background-color": "#e9f0f3" },
    },
  ],
};

export function MapShell() {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current) return;
    const configuredStyle = import.meta.env.VITE_MAP_STYLE_URL as
      string | undefined;
    const map = new maplibregl.Map({
      container: container.current,
      style: configuredStyle || offlineStyle,
      center: [-99.4, 31.0],
      zoom: 4.6,
      attributionControl: false,
    });
    map.addControl(
      new maplibregl.NavigationControl({ showCompass: false }),
      "top-right",
    );
    return () => map.remove();
  }, []);

  return (
    <section className="map-panel" aria-labelledby="map-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Spatial workspace</p>
          <h2 id="map-heading">Radio site map</h2>
        </div>
        <span className="status-chip">Map shell ready</span>
      </div>
      <div
        ref={container}
        className="map"
        data-testid="map"
        aria-label="Radio site planning map"
      />
      <p className="map-note">
        Neutral offline style loaded. Configure a MapLibre style URL to add a
        base map.
      </p>
    </section>
  );
}
