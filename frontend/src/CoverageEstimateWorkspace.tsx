import { type FormEvent, useEffect, useMemo, useState } from "react";

import {
  approveCoverageEstimate,
  createCoverageEstimate,
  getCoverageEngineStatus,
  listCoverageEstimates,
  listHAATCalculations,
} from "./api";
import type {
  CoverageEngineStatus,
  CoverageEstimate,
  HAATCalculation,
  Incident,
} from "./types";

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

function readable(value: string): string {
  return value.replaceAll("_", " ");
}

function distance(value: number | null): string {
  if (value === null) return "Not produced";
  return `${(value / 1000).toFixed(1)} km`;
}

function configurationApproved(
  engine: CoverageEngineStatus | null,
  estimate: CoverageEstimate,
): boolean {
  return (engine?.approved_presets ?? []).some(
    (approval) =>
      approval.preset === estimate.preset &&
      approval.preset_version === estimate.preset_version,
  );
}

export function CoverageEstimateWorkspace({
  incident,
}: {
  incident?: Incident;
}) {
  const [engine, setEngine] = useState<CoverageEngineStatus | null>(null);
  const [haatCalculations, setHAATCalculations] = useState<HAATCalculation[]>(
    [],
  );
  const [estimates, setEstimates] = useState<CoverageEstimate[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const canEdit = incident?.permissions.includes("rf.edit") ?? false;
  const canApprove = incident?.permissions.includes("rf.approve") ?? false;
  const approvedHAAT = useMemo(
    () =>
      haatCalculations.filter(
        (calculation) =>
          calculation.status === "approved" &&
          calculation.calculation_state === "complete" &&
          calculation.haat_m !== null,
      ),
    [haatCalculations],
  );

  useEffect(() => {
    let active = true;
    if (!incident) {
      setEngine(null);
      setHAATCalculations([]);
      setEstimates([]);
      setError("");
      return;
    }
    setLoading(true);
    setError("");
    Promise.all([
      getCoverageEngineStatus(),
      listHAATCalculations(incident.id),
      listCoverageEstimates(incident.id),
    ])
      .then(([nextEngine, nextHAAT, nextEstimates]) => {
        if (!active) return;
        setEngine(nextEngine);
        setHAATCalculations(nextHAAT);
        setEstimates(nextEstimates);
      })
      .catch((loadError: unknown) => {
        if (active)
          setError(
            errorMessage(loadError, "Unable to load coverage-estimate data."),
          );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [incident]);

  async function refreshEstimates() {
    if (!incident) return;
    setEstimates(await listCoverageEstimates(incident.id));
    window.dispatchEvent(new Event("ict-coverage-estimates-updated"));
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!incident || !canEdit) return;
    const data = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      await createCoverageEstimate({
        haat_calculation: String(data.get("haat_calculation")),
        environment: String(
          data.get("environment"),
        ) as CoverageEstimate["environment"],
        preset: String(data.get("preset")),
      });
      await refreshEstimates();
    } catch (submitError) {
      setError(
        errorMessage(submitError, "Unable to create coverage estimate."),
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleApprove(estimate: CoverageEstimate) {
    if (!canApprove || estimate.calculation_state !== "complete") return;
    if (
      !window.confirm(
        "Approve and lock this provisional planning estimate with its exact input, model, and result digests?",
      )
    )
      return;
    setBusy(true);
    setError("");
    try {
      await approveCoverageEstimate(estimate.id);
      await refreshEstimates();
    } catch (approvalError) {
      setError(
        errorMessage(approvalError, "Unable to approve coverage estimate."),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="coverage-panel" aria-labelledby="coverage-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Explainable decision support</p>
          <h2 id="coverage-heading">Band and environment estimates</h2>
        </div>
        <span className="count">{estimates.length}</span>
      </div>
      <p className="panel-intro">
        Compare a provisional link-budget and radio-horizon estimate by band and
        operating environment. Manual Phase 1 rings remain separate. These
        results are planning estimates—not propagation studies, coordination
        decisions, spectrum authorization, or coverage guarantees.
      </p>

      {!incident ? (
        <p className="empty">
          Select an incident to review calculated planning estimates.
        </p>
      ) : loading ? (
        <p role="status" aria-live="polite">
          Loading coverage-estimate configuration…
        </p>
      ) : (
        <>
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}

          {engine && (
            <article className="coverage-engine-card">
              <div>
                <strong>{engine.engine_version}</strong>
                <span>
                  {engine.approved_for_operational_use
                    ? "Approved configuration"
                    : "Provisional configuration—practitioner review required"}
                </span>
              </div>
              <p>{engine.disclaimer}</p>
              <details>
                <summary>Supported bands, margins, and presets</summary>
                <p>
                  Supported groups:{" "}
                  {(engine.supported_band_groups ?? [])
                    .map((band) => readable(band.name))
                    .join(", ")}
                  .
                </p>
                <dl className="provenance-grid">
                  {(engine.environments ?? []).map((environment) => (
                    <div key={environment.name}>
                      <dt>{readable(environment.name)}</dt>
                      <dd>{environment.additional_margin_db} dB margin</dd>
                    </div>
                  ))}
                </dl>
              </details>
            </article>
          )}

          {canEdit && (
            <form className="coverage-form" onSubmit={handleCreate}>
              <h3>New provisional estimate</h3>
              <p className="form-note">
                Select a complete, approved HAAT calculation. The estimate
                snapshots its RF input digest, HAAT result digest, site
                coordinates, model version, preset, assumptions, and output.
              </p>
              <label>
                Approved HAAT calculation
                <select
                  name="haat_calculation"
                  required
                  disabled={approvedHAAT.length === 0}
                >
                  <option value="">Select approved HAAT evidence</option>
                  {approvedHAAT.map((calculation) => (
                    <option key={calculation.id} value={calculation.id}>
                      {calculation.site_name} · {calculation.rf_input_label} ·
                      HAAT {calculation.haat_m} m
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Operating environment
                <select name="environment" defaultValue="suburban">
                  {(engine?.environments ?? []).map((environment) => (
                    <option key={environment.name} value={environment.name}>
                      {readable(environment.name)} ·{" "}
                      {environment.additional_margin_db} dB provisional margin
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Estimate preset
                <select name="preset" defaultValue="balanced">
                  {Object.entries(engine?.presets ?? {}).map(
                    ([name, preset]) => (
                      <option key={name} value={name}>
                        {readable(name)} · {preset.version}
                      </option>
                    ),
                  )}
                </select>
              </label>
              <button
                type="submit"
                disabled={
                  busy ||
                  approvedHAAT.length === 0 ||
                  Object.keys(engine?.presets ?? {}).length === 0
                }
              >
                Create explainable estimate
              </button>
              {approvedHAAT.length === 0 && (
                <p className="warning-text">
                  Approve a complete HAAT calculation before creating an
                  estimate.
                </p>
              )}
            </form>
          )}

          <div className="coverage-results">
            <h3>Estimate history</h3>
            {estimates.length === 0 ? (
              <p className="empty">No calculated estimates exist.</p>
            ) : (
              <div
                className="table-scroll"
                role="region"
                aria-label="Coverage estimate table"
              >
                <table>
                  <caption>
                    Provisional results with a sensitivity range; manual rings
                    are not included.
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Site</th>
                      <th scope="col">Band / environment</th>
                      <th scope="col">Conservative</th>
                      <th scope="col">Nominal</th>
                      <th scope="col">Optimistic</th>
                      <th scope="col">State</th>
                      <th scope="col">Evidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {estimates.map((estimate) => (
                      <tr key={estimate.id}>
                        <th scope="row">{estimate.site_name}</th>
                        <td>
                          {readable(estimate.band)} /{" "}
                          {readable(estimate.environment)}
                        </td>
                        <td>{distance(estimate.conservative_distance_m)}</td>
                        <td>{distance(estimate.nominal_distance_m)}</td>
                        <td>{distance(estimate.optimistic_distance_m)}</td>
                        <td>
                          {readable(estimate.calculation_state)} ·{" "}
                          {estimate.status}
                        </td>
                        <td>
                          <details>
                            <summary>Explanation and digests</summary>
                            <p>{estimate.explanation}</p>
                            {estimate.warnings.map((warning) => (
                              <p className="warning-text" key={warning}>
                                {warning}
                              </p>
                            ))}
                            {estimate.exclusions.map((exclusion) => (
                              <p
                                className="warning-text"
                                key={exclusion.reason}
                              >
                                {exclusion.code}: {exclusion.reason}
                              </p>
                            ))}
                            <dl className="digest-list">
                              <div>
                                <dt>Engine</dt>
                                <dd>{estimate.engine_version}</dd>
                              </div>
                              <div>
                                <dt>Preset</dt>
                                <dd>{estimate.preset_version}</dd>
                              </div>
                              <div>
                                <dt>RF input digest</dt>
                                <dd>{estimate.input_sha256}</dd>
                              </div>
                              <div>
                                <dt>HAAT result digest</dt>
                                <dd>{estimate.haat_result_sha256}</dd>
                              </div>
                              <div>
                                <dt>Estimate result digest</dt>
                                <dd>{estimate.result_sha256}</dd>
                              </div>
                            </dl>
                            {canApprove &&
                              estimate.status === "draft" &&
                              estimate.calculation_state === "complete" &&
                              configurationApproved(engine, estimate) && (
                                <button
                                  type="button"
                                  disabled={busy}
                                  onClick={() => void handleApprove(estimate)}
                                >
                                  Approve and lock estimate
                                </button>
                              )}
                            {canApprove &&
                              estimate.status === "draft" &&
                              estimate.calculation_state === "complete" &&
                              !configurationApproved(engine, estimate) && (
                                <p className="warning-text">
                                  This exact engine and preset version has not
                                  passed the configured qualified-practitioner
                                  approval gate. The draft evidence can be
                                  reviewed but not approved.
                                </p>
                              )}
                          </details>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </section>
  );
}
