import "maplibre-gl/dist/maplibre-gl.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import { registerOfflineServiceWorker } from "./serviceWorker";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

window.addEventListener("load", () => {
  void registerOfflineServiceWorker();
});
