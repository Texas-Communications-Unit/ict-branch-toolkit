import "maplibre-gl/dist/maplibre-gl.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import { ElevationEnhancer } from "./ElevationEnhancer";
import { IncidentMetadataEditor } from "./IncidentMetadataEditor";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
    <ElevationEnhancer />
    <IncidentMetadataEditor />
  </StrictMode>,
);
