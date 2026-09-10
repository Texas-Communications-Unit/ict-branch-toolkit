import "maplibre-gl/dist/maplibre-gl.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import { ElevationEnhancer } from "./ElevationEnhancer";
import { FccUnitEnhancer } from "./FccUnitEnhancer";
import { IncidentMetadataEditor } from "./IncidentMetadataEditor";
import { MapObjectSelectionEnhancer } from "./MapObjectSelectionEnhancer";
import "./mapObjectSelection.css";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
    <ElevationEnhancer />
    <FccUnitEnhancer />
    <IncidentMetadataEditor />
    <MapObjectSelectionEnhancer />
  </StrictMode>,
);
