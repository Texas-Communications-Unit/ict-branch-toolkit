import { type FormEvent, useEffect, useMemo, useState } from "react";

import {
  approveHAATCalculation,
  createHAATCalculation,
  getElevationProviderStatus,
  listHAATCalculations,
  listRadioSites,
  listRFAnalysisInputSnapshots,
  retryHAATCalculation,
} from "./api";
import type {
  ElevationProviderStatus,
  HAATCalculation,
  Incident,
  RFAnalysisInputSnapshot,
  RadioSite,
} from "./types";

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

function stateLabel(state: string): string {
  return state.replaceAll("_", " ");
}

export function HAATWorkspace({ incident }: { incident?: Incident }) {
  const [provider, setProvider] = useState<ElevationProviderStatus | null>(
    null,
  );
  const [sites, setSites] = useState<RadioSite[]>([]);
  const [rfSnapshots, setRFSnapshots] = useState<RFAnalysisInputSnapshot[]>([]);
  const [calculations, setCalculations] = useState<HAATCalculation[]>([]);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const canEdit = incident?.permissions.includes("rf.edit") ?? false;
  const canApprove = incident?.permissions.includes("rf.approve") ?? false;
  const usableSnapshots = useMemo(
    () =>
      rfSnapshots.filter((snapshot) => {
        const inputs = snapshot.input_snapshot.inputs;
        return (
          typeof inputs === "object" &&
          inputs !== null &&
          "antenna_center_agl_m" in inputs &&
          inputs.antenna_center_agl_m !== null
        );
      }),
    [rfSnapshots],
  );

  useEffect(() => {
    let active = true;
    if (!incident) {
      setProvider(null);
      setSites([]);
      setRFSnapshots([]);
      setCalculations([]);
      setError("");
      return;
    }
    setLoading(true);
    setError("");
    Promise.all([
      getElevationProviderStatus(),
      listRadioSites(incident.id),
      listRFAnalysisInputSnapshots(incident.id),
      listHAATCalculations(incident.id),
    ])
      .then(([nextProvider, nextSites, nextSnapshots, nextCalculations]) => {
        if (!active) return;
        setProvider(nextProvider);
        setSites(nextSites);
        setRFSnapshots(nextSnapshots);
        setCalculations(nextCalculations);
      })
      .catch((loadError: unknown) => {
        if (active)
          setError(
            errorMessage(loadError, "Unable to load elevation and HAAT data."),
          );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [incident]);

  async function refreshCalculations() {
    if (!incident) return;
    setCalculations(await listHAATCalculations(incident.id));
  }

  async function refreshInputs() {
    if (!incident) return;
    setLoading(true);
    setError("");
    try {
      const [nextProvider, nextSites, nextSnapshots, nextCalculations] =
        await Promise.all([
          getElevationProviderStatus(),
          listRadioSites(incident.id),
          listRFAnalysisInputSnapshots(incident.id),
          listHAATCalculations(incident.id),
        ]);
      setProvider(nextProvider);
      setSites(nextSites);
      setRFSnapshots(nextSnapshots);
      setCalculations(nextCalculations);
    } catch (loadError) {
      setError(
        errorMessage(loadError, "Unable to refresh elevation and HAAT data."),
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!incident || !canEdit || !provider?.available) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true);
    setError("");
    try {
      await createHAATCalculation({
        site: String(data.get("site")),
        rf_input_snapshot: String(data.get("rf_input_snapshot")),
        radial_count: Number(data.get("radial_count")),
        start_azimuth_deg: String(data.get("start_azimuth_deg")),
        sampling_interval_m: Number(data.get("sampling_interval_m")),
        inner_distance_m: Number(data.get("inner_distance_m")),
        outer_distance_m: Number(data.get("outer_distance_m")),
        rounding_m: String(data.get("rounding_m")),
        force_refresh: data.get("force_refresh") === "on",
      });
      await refreshCalculations();
    } catch (submitError) {
      setError(errorMessage(submitError, "Unable to calculate HAAT."));
    } finally {
      setBusy(false);
    }
  }

  async function handleRetry(calculation: HAATCalculation) {
    if (!canEdit) return;
    setBusy(true);
    setError("");
    try {
      await retryHAATCalculation(calculation.id);
      await refreshCalculations();
    } catch (retryError) {
      setError(
        errorMessage(retryError, "Unable to retry elevation retrieval."),
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleApprove(calculation: HAATCalculation) {
    if (!canApprove) return;
    if (
      !window.confirm(
        "Approve and lock this complete HAAT result with its exact source and algorithm snapshot?",
      )
    )
      return;
    setBusy(true);
    setError("");
    try {
      await approveHAATCalculation(calculation.id);
      await refreshCalculations();
    } catch (approvalError) {
      setError(errorMessage(approvalError, "Unable to approve HAAT result."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="haat-panel" aria-labelledby="haat-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Source-aware terrain</p>
          <h2 id="haat-heading">Elevation and HAAT</h2>
        </div>
        <span className="count">{calculations.length}</span>
      </div>
      <p className="panel-intro">
        Calculate reproducible height above average terrain (HAAT) from an
        approved elevation source. Results are planning decision support—not a
        propagation study, regulatory method determination, or coverage
        guarantee.
      </p>

      {!incident ? (
        <p className="empty">
          Select an incident to review elevation sources and HAAT results.
        </p>
      ) : loading ? (
        <p role="status" aria-live="polite">
          Loading elevation configuration…
        </p>
      ) : (
        <>
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}

          <article
            className={`elevation-provider-card ${
              provider?.available ? "available" : "unavailable"
            }`}
          >
            <div>
              <strong>
                {provider?.dataset_product ?? "Elevation source unavailable"}
              </strong>
              <span>
                Provider: {provider?.provider ?? "unknown"} ·{" "}
                {provider?.offline ? "offline capable" : "network dependent"}
              </span>
            </div>
            <span
              className={`state-badge ${
                provider?.available ? "complete" : "unavailable"
              }`}
            >
              {provider?.available ? "approved and available" : "not available"}
            </span>
            {provider?.warning && (
              <p className="warning-text">{provider.warning}</p>
            )}
            <button
              className="secondary-button"
              type="button"
              disabled={loading || busy}
              onClick={() => void refreshInputs()}
            >
              Refresh sites, RF snapshots, and source status
            </button>
            {provider?.available && (
              <details>
                <summary>Source approval and reference details</summary>
                <dl className="provenance-grid">
                  <div>
                    <dt>Source version</dt>
                    <dd>{provider.source_version || "retrieval-dated"}</dd>
                  </div>
                  <div>
                    <dt>Horizontal reference</dt>
                    <dd>{provider.horizontal_crs}</dd>
                  </div>
                  <div>
                    <dt>Vertical reference</dt>
                    <dd>
                      {provider.vertical_crs} → {provider.target_vertical_crs}
                    </dd>
                  </div>
                  <div>
                    <dt>Nominal resolution</dt>
                    <dd>
                      {provider.resolution_m
                        ? `${provider.resolution_m} m`
                        : "not supplied"}
                    </dd>
                  </div>
                </dl>
                <p>{provider.permitted_use}</p>
                {provider.license_terms_url && (
                  <a href={provider.license_terms_url}>
                    Source license or terms
                  </a>
                )}
              </details>
            )}
          </article>

          {canEdit && (
            <form className="haat-form" onSubmit={handleCreate}>
              <h3>New reproducible calculation</h3>
              <p className="form-note">
                The selected approved RF input snapshot must contain an explicit
                antenna-center AGL height. No operational defaults are inferred.
              </p>
              <label>
                Radio site
                <select name="site" required disabled={sites.length === 0}>
                  <option value="">Select a site</option>
                  {sites.map((site) => (
                    <option key={site.id} value={site.id}>
                      {site.name} · {site.latitude}, {site.longitude}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Approved RF input snapshot with antenna AGL
                <select
                  name="rf_input_snapshot"
                  required
                  disabled={usableSnapshots.length === 0}
                >
                  <option value="">Select an approved RF snapshot</option>
                  {usableSnapshots.map((snapshot) => (
                    <option key={snapshot.id} value={snapshot.id}>
                      {snapshot.label} · AGL{" "}
                      {String(
                        (
                          snapshot.input_snapshot.inputs as Record<
                            string,
                            unknown
                          >
                        ).antenna_center_agl_m,
                      )}{" "}
                      m
                    </option>
                  ))}
                </select>
                {rfSnapshots.length > 0 && usableSnapshots.length === 0 && (
                  <small>
                    Create an approved RF input snapshot whose profile version
                    includes antenna-center AGL.
                  </small>
                )}
              </label>
              <fieldset>
                <legend>General radial-average terrain method</legend>
                <label>
                  Radial count
                  <input
                    name="radial_count"
                    type="number"
                    min="4"
                    max="360"
                    defaultValue="8"
                    required
                  />
                </label>
                <label>
                  Starting azimuth (degrees)
                  <input
                    name="start_azimuth_deg"
                    type="number"
                    min="0"
                    max="359.999"
                    step="0.001"
                    defaultValue="0"
                    required
                  />
                </label>
                <label>
                  Inner distance (m)
                  <input
                    name="inner_distance_m"
                    type="number"
                    min="1"
                    max="100000"
                    defaultValue="3000"
                    required
                  />
                </label>
                <label>
                  Outer distance (m)
                  <input
                    name="outer_distance_m"
                    type="number"
                    min="1"
                    max="100000"
                    defaultValue="16000"
                    required
                  />
                </label>
                <label>
                  Sampling interval (m)
                  <input
                    name="sampling_interval_m"
                    type="number"
                    min="10"
                    max="100000"
                    defaultValue="1000"
                    required
                  />
                </label>
                <label>
                  Rounding increment (m)
                  <input
                    name="rounding_m"
                    type="number"
                    min="0.001"
                    max="100"
                    step="0.001"
                    defaultValue="0.1"
                    required
                  />
                </label>
              </fieldset>
              <label className="checkbox-label">
                <input name="force_refresh" type="checkbox" />
                Bypass an unexpired cache entry and retrieve a fresh source
                snapshot
              </label>
              <button
                type="submit"
                disabled={
                  busy ||
                  !provider?.available ||
                  sites.length === 0 ||
                  usableSnapshots.length === 0
                }
              >
                Calculate elevation and HAAT
              </button>
            </form>
          )}

          <div className="haat-results">
            <h3>Calculation history</h3>
            {calculations.length === 0 ? (
              <p className="empty">No HAAT calculations are recorded.</p>
            ) : (
              calculations.map((calculation) => (
                <article className="haat-result-card" key={calculation.id}>
                  <div className="haat-result-heading">
                    <div>
                      <strong>{calculation.site_name}</strong>
                      <span>
                        {calculation.profile_name} · version{" "}
                        {calculation.profile_version_number}
                      </span>
                      <span>RF snapshot: {calculation.rf_input_label}</span>
                    </div>
                    <div className="state-badges">
                      <span
                        className={`state-badge ${calculation.calculation_state}`}
                      >
                        {stateLabel(calculation.calculation_state)}
                      </span>
                      <span className={`status ${calculation.status}`}>
                        {calculation.status}
                      </span>
                    </div>
                  </div>
                  <dl className="haat-measurements">
                    <div>
                      <dt>Site elevation</dt>
                      <dd>
                        {calculation.site_elevation_m
                          ? `${calculation.site_elevation_m} m`
                          : "unavailable"}
                      </dd>
                    </div>
                    <div>
                      <dt>Antenna AMSL</dt>
                      <dd>
                        {calculation.antenna_amsl_m
                          ? `${calculation.antenna_amsl_m} m`
                          : "unavailable"}
                      </dd>
                    </div>
                    <div>
                      <dt>Average terrain</dt>
                      <dd>
                        {calculation.average_terrain_m
                          ? `${calculation.average_terrain_m} m`
                          : "unavailable"}
                      </dd>
                    </div>
                    <div className="haat-primary-value">
                      <dt>HAAT</dt>
                      <dd>
                        {calculation.haat_m
                          ? `${calculation.haat_m} m`
                          : "not calculated"}
                      </dd>
                    </div>
                  </dl>
                  {calculation.warnings.length > 0 && (
                    <div className="haat-warnings" role="note">
                      <strong>Warnings and limitations</strong>
                      <ul>
                        {calculation.warnings.map((warning, index) => (
                          <li key={`${calculation.id}-warning-${index}`}>
                            {warning}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  <details>
                    <summary>Reproducibility and source provenance</summary>
                    <dl className="provenance-grid">
                      <div>
                        <dt>Method version</dt>
                        <dd>{calculation.method_version}</dd>
                      </div>
                      <div>
                        <dt>Elevation state</dt>
                        <dd>
                          {stateLabel(calculation.elevation.current_state)}
                        </dd>
                      </div>
                      <div>
                        <dt>Provider / product</dt>
                        <dd>
                          {calculation.elevation.provider} ·{" "}
                          {calculation.elevation.dataset_product}
                        </dd>
                      </div>
                      <div>
                        <dt>Source version</dt>
                        <dd>
                          {calculation.elevation.source_version ||
                            new Date(
                              calculation.elevation.retrieved_at,
                            ).toLocaleString()}
                        </dd>
                      </div>
                      <div>
                        <dt>Vertical transformation</dt>
                        <dd>
                          {calculation.elevation.vertical_crs} →{" "}
                          {calculation.elevation.target_vertical_crs}
                        </dd>
                      </div>
                      <div>
                        <dt>Samples</dt>
                        <dd>
                          {calculation.sample_count} used ·{" "}
                          {calculation.excluded_sample_count} excluded
                        </dd>
                      </div>
                    </dl>
                    <p>
                      {String(
                        calculation.algorithm_snapshot.method_scope ?? "",
                      )}
                    </p>
                    <p>
                      Result SHA-256: <code>{calculation.result_sha256}</code>
                    </p>
                    <p>
                      Elevation samples SHA-256:{" "}
                      <code>{calculation.elevation.sample_sha256}</code>
                    </p>
                    <pre>
                      {JSON.stringify(calculation.algorithm_snapshot, null, 2)}
                    </pre>
                  </details>
                  <div className="button-row">
                    {canEdit && (
                      <button
                        className="secondary-button"
                        type="button"
                        disabled={busy || !provider?.available}
                        onClick={() => void handleRetry(calculation)}
                      >
                        Retry with fresh elevation data
                      </button>
                    )}
                    {canApprove &&
                      calculation.status === "draft" &&
                      calculation.calculation_state === "complete" && (
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => void handleApprove(calculation)}
                        >
                          Approve and lock result
                        </button>
                      )}
                  </div>
                </article>
              ))
            )}
          </div>
        </>
      )}
    </section>
  );
}
