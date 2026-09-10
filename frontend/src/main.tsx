import "maplibre-gl/dist/maplibre-gl.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import { ElevationEnhancer } from "./ElevationEnhancer";
import { FccUnitEnhancer } from "./FccUnitEnhancer";
import { IncidentMetadataEditor } from "./IncidentMetadataEditor";
import { LocationSearchEnhancer } from "./LocationSearchEnhancer";
import { MapObjectSelectionEnhancer } from "./MapObjectSelectionEnhancer";
import { NifogResourceCategoriesEnhancer } from "./NifogResourceCategoriesEnhancer";
import "./mapObjectSelection.css";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
    <ElevationEnhancer />
    <FccUnitEnhancer />
    <IncidentMetadataEditor />
    <LocationSearchEnhancer />
    <MapObjectSelectionEnhancer />
    <NifogResourceCategoriesEnhancer />
  </StrictMode>,
);
