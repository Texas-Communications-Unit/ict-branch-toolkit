import { FormEvent, useState } from "react";

import { searchFccAntennaStructures, searchFccLicenses } from "./api";
import type { FccAntennaStructure, FccLicenseSearchResult } from "./types";

export function FccReferenceWorkspace() {
  const [kind, setKind] = useState<"licenses" | "structures">("licenses");
  const [licenses, setLicenses] = useState<FccLicenseSearchResult[]>([]);
  const [structures, setStructures] = useState<FccAntennaStructure[]>([]);
  const [message, setMessage] = useState(
    "Enter search criteria to query the imported FCC reference data.",
  );
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const params = {
      search: String(form.get("search") ?? ""),
      state: String(form.get("state") ?? ""),
      service_code: String(form.get("service_code") ?? ""),
      status: String(form.get("status") ?? ""),
    };
    setBusy(true);
    try {
      if (kind === "licenses") {
        const result = await searchFccLicenses(params);
        setLicenses(result.results);
        setMessage(
          `${result.count} FCC license record${result.count === 1 ? "" : "s"} found.`,
        );
      } else {
        const result = await searchFccAntennaStructures({
          search: params.search,
          status: params.status,
        });
        setStructures(result.results);
        setMessage(
          `${result.count} antenna structure record${result.count === 1 ? "" : "s"} found.`,
        );
      }
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "The FCC reference search failed.",
      );
    } finally {
      setBusy(false);
    }
  }

  const results = kind === "licenses" ? licenses : structures;
  return (
    <section className="library-panel" aria-labelledby="fcc-reference-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Public reference data</p>
          <h2 id="fcc-reference-heading">FCC Reference Search</h2>
        </div>
      </div>
      <p>
        Search imported government and commercial land-mobile licenses or
        Antenna Structure Registration records. Results retain their FCC archive
        provenance.
      </p>
      <form className="import-panel" onSubmit={submit}>
        <fieldset>
          <legend>Record type</legend>
          <label>
            <input
              type="radio"
              name="kind"
              checked={kind === "licenses"}
              onChange={() => setKind("licenses")}
            />{" "}
            Licenses
          </label>{" "}
          <label>
            <input
              type="radio"
              name="kind"
              checked={kind === "structures"}
              onChange={() => setKind("structures")}
            />{" "}
            Antenna structures
          </label>
        </fieldset>
        <label>
          Search term
          <input
            name="search"
            type="search"
            placeholder={
              kind === "licenses"
                ? "Call sign, licensee, FRN, or city"
                : "Registration, owner, FRN, FAA study, or type"
            }
          />
        </label>
        {kind === "licenses" && (
          <>
            <label>
              State
              <input name="state" maxLength={2} placeholder="TX" />
            </label>
            <label>
              Radio service code
              <input name="service_code" maxLength={8} placeholder="PW" />
            </label>
          </>
        )}
        <label>
          Status code
          <input name="status" maxLength={8} placeholder="A" />
        </label>
        <button type="submit" disabled={busy}>
          {busy ? "Searching…" : "Search FCC records"}
        </button>
      </form>
      <p role="status" aria-live="polite">
        {message}
      </p>
      {results.length > 0 && (
        <div className="resource-grid">
          {kind === "licenses"
            ? licenses.map((item) => (
                <article className="resource-card" key={item.id}>
                  <strong>
                    {item.call_sign} ·{" "}
                    {item.licensee_name || "Unnamed licensee"}
                  </strong>
                  <span>
                    {item.city}
                    {item.city && item.state ? ", " : ""}
                    {item.state} · Service {item.radio_service_code} · Status{" "}
                    {item.license_status}
                  </span>
                  <span>
                    {item.frequencies_hz
                      .slice(0, 5)
                      .map((hz) => `${(hz / 1_000_000).toFixed(6)} MHz`)
                      .join(" · ") || "No frequency records"}
                  </span>
                  <small>
                    {item.batch.dataset_label} · retrieved{" "}
                    {new Date(item.batch.retrieved_at).toLocaleDateString()} ·{" "}
                    {item.frequency_count} frequencies
                  </small>
                </article>
              ))
            : structures.map((item) => (
                <article className="resource-card" key={item.id}>
                  <strong>
                    ASR {item.registration_number} ·{" "}
                    {item.owner_name || "Owner not listed"}
                  </strong>
                  <span>
                    {item.structure_type || "Structure type not listed"} ·
                    Status {item.status_code || "not listed"}
                  </span>
                  <span>
                    {item.latitude && item.longitude
                      ? `${item.latitude}, ${item.longitude}`
                      : "Coordinates not listed"}
                  </span>
                  <small>
                    {item.batch.dataset_label} · retrieved{" "}
                    {new Date(item.batch.retrieved_at).toLocaleDateString()}
                  </small>
                </article>
              ))}
        </div>
      )}
      <p className="empty">
        <strong>Decision-support notice:</strong> FCC reference data does not
        authorize frequency use, transmission, coordination, or site access.
        Confirm current licensing and applicable authority before operational
        use.
      </p>
    </section>
  );
}
