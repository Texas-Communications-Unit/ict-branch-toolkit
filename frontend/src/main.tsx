import "maplibre-gl/dist/maplibre-gl.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import { ElevationEnhancer } from "./ElevationEnhancer";
import { FccUnitEnhancer } from "./FccUnitEnhancer";
import { ICS205BWorkspace } from "./ICS205BWorkspace";
import { IncidentMetadataEditor } from "./IncidentMetadataEditor";
import { LocationSearchEnhancer } from "./LocationSearchEnhancer";
import { MapObjectSelectionEnhancer } from "./MapObjectSelectionEnhancer";
import { NifogResourceCategoriesEnhancer } from "./NifogResourceCategoriesEnhancer";
import { registerWorkspaceTab } from "./workspaceTabRegistry";
import "./mapObjectSelection.css";
import "./NifogResourceCategories.css";
import "./styles.css";

registerWorkspaceTab({
  id: "ics-205b",
  label: "ICS 205B",
  layout: "single",
  content: <ICS205BWorkspace />,
});

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
