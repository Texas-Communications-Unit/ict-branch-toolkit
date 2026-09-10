import { FormEvent, useEffect, useState } from "react";
import { createPortal } from "react-dom";

import {
  type LocationSearchResult,
  resolveLocation,
} from "./locationSearchApi";

function populateCanonicalCoordinate(result: LocationSearchResult) {
  const panel = document.querySelector<HTMLElement>("section.map-panel");
  if (!panel) return false;

  const input = panel.querySelector<HTMLInputElement>(
    'input[placeholder="33.214500, -97.133100"]',
  );
  if (!input) return false;
  const setter = Object.getOwnPropertyDescriptor(
    HTMLInputElement.prototype,
    "value",
  )?.set;
  setter?.call(input, result.formats.decimal);
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.dispatchEvent(new Event("change", { bubbles: true }));
  window.dispatchEvent(
    new CustomEvent("ict-location-resolved", { detail: result }),
  );
  queueMicrotask(() => {
    const preview = Array.from(
      panel.querySelectorAll<HTMLButtonElement>("button"),
    ).find((button) => button.textContent?.trim() === "Parse and preview");
    preview?.click();
  });
  return true;
}

export function LocationSearchEnhancer() {
  const [mount, setMount] = useState<HTMLElement | null>(null);
  const [query, setQuery] = useState("");
  const [allowExternal, setAllowExternal] = useState(false);
  const [results, setResults] = useState<LocationSearchResult[]>([]);
  const [status, setStatus] = useState(
    "Coordinates are resolved locally first. External lookup is off by default.",
  );
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const locate = () => {
      const heading = document.getElementById("map-heading");
      setMount(heading?.closest<HTMLElement>("section.map-panel") ?? null);
    };
    locate();
    const observer = new MutationObserver(locate);
    observer.observe(document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    try {
      const response = await resolveLocation(query, allowExternal);
      setResults(response.results);
      if (response.results.length) {
        setStatus(
          `${response.results.length} normalized WGS 84 result${response.results.length === 1 ? "" : "s"} available. Select one to preview it on the map.`,
        );
      } else if (response.blocked_reason) {
        setStatus(
          `${response.blocked_reason} Enable external lookup only after confirming the query is appropriate to send to the configured provider.`,
        );
      } else if (!response.configured) {
        setStatus(
          "No approved provider is configured for this input. Coordinate parsing remains available.",
        );
      } else {
        setStatus("No matching location was returned.");
      }
    } catch (error) {
      setResults([]);
      setStatus(error instanceof Error ? error.message : "Location search failed.");
    } finally {
      setBusy(false);
    }
  }

  function select(result: LocationSearchResult) {
    const applied = populateCanonicalCoordinate(result);
    setStatus(
      applied
        ? `Selected ${result.label}. Normalized coordinate ${result.formats.decimal} was sent to the existing map preview workflow.`
        : `Selected ${result.label}: ${result.formats.decimal}. The map coordinate field is not currently available.`,
    );
  }

  if (!mount) return null;

  return createPortal(
    <section className="location-search-panel" aria-labelledby="location-search-heading">
      <h3 id="location-search-heading">Map location search</h3>
      <p>
        Enter an address, intersection, decimal coordinate, DDM, DMS, MGRS/USNG,
        a copied Google Maps coordinate URL, or a what3words address. Successful
        results are normalized to WGS 84 while your original entry is preserved.
      </p>
      <form onSubmit={submit}>
        <label>
          Location
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            required
            maxLength={500}
            placeholder="Address, intersection, coordinates, or ///words.words.words"
          />
        </label>
        <label className="location-search-external-consent">
          <input
            type="checkbox"
            checked={allowExternal}
            onChange={(event) => setAllowExternal(event.target.checked)}
          />{" "}
          Allow this query to be sent to the configured external location provider
        </label>
        <p className="empty">
          Leave external lookup off for protected or sensitive operational
          locations unless an appropriate privacy/operational determination has
          been made. Coordinate syntax is always parsed locally first.
        </p>
        <button type="submit" className="secondary-button" disabled={busy}>
          {busy ? "Resolving…" : "Resolve location"}
        </button>
      </form>
      <p role="status" aria-live="polite">
        {status}
      </p>
      {results.length > 0 && (
        <ul className="location-search-results" aria-label="Normalized location results">
          {results.map((result, index) => (
            <li key={`${result.provider}-${result.latitude}-${result.longitude}-${index}`}>
              <button
                type="button"
                className="secondary-button"
                onClick={() => select(result)}
              >
                <strong>{result.label}</strong>
                <span>{result.formats.decimal} · WGS 84</span>
                <small>Provider: {result.provider}</small>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>,
    mount,
  );
}
