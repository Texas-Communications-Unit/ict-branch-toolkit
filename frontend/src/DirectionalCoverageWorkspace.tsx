import { type FormEvent, useEffect, useMemo, useState } from "react";

import {
  approveDirectionalCoverageAnalysis,
  createDirectionalCoverageAnalysis,
  getCoverageEngineStatus,
  getDirectionalAnalysisStatus,
  listDirectionalCoverageAnalyses,
  listHAATCalculations,
  listRFAnalysisInputSnapshots,
} from "./api";
import type {
  CoverageEngineStatus,
  DirectionalAnalysisStatus,
  DirectionalCoverageAnalysis,
  HAATCalculation,
  Incident,
  RFAnalysisInputSnapshot,
} from "./types";

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

function readable(value: string): string {
  return value.replaceAll("_", " ");
}

function distance(value: number | null): string {
  return value === null ? "Not produced" : `${(value / 1000).toFixed(1)} km`;
}

function configurationApproved(
  status: DirectionalAnalysisStatus | null,
  engine: CoverageEngineStatus | null,
  analysis: DirectionalCoverageAnalysis,
): boolean {
  return (
    (status?.approved_for_operational_use ?? false) &&
    (engine?.approved_presets ?? []).some(
      (approval) =>
        approval.preset === analysis.preset &&
        approval.preset_version === analysis.preset_version,
    )
  );
}

export function DirectionalCoverageWorkspace({
  incident,
}: {
  incident?: Incident;
}) {
  const [status, setStatus] = useState<DirectionalAnalysisStatus | null>(null);
  const [engine, setEngine] = useState<CoverageEngineStatus | null>(null);
  const [haatCalculations, setHAATCalculations] = useState<HAATCalculation[]>(
    [],
  );
  const [snapshots, setSnapshots] = useState<RFAnalysisInputSnapshot[]>([]);
  const [analyses, setAnalyses] = useState<DirectionalCoverageAnalysis[]>([]);
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
      setStatus(null);
      setEngine(null);
      setHAATCalculations([]);
      setSnapshots([]);
      setAnalyses([]);
      setError("");
      return;
    }
    setLoading(true);
    setError("");
    Promise.all([
      getDirectionalAnalysisStatus(),
      getCoverageEngineStatus(),
      listHAATCalculations(incident.id),
      listRFAnalysisInputSnapshots(incident.id),
      listDirectionalCoverageAnalyses(incident.id),
    ])
      .then(
        ([nextStatus, nextEngine, nextHAAT, nextSnapshots, nextAnalyses]) => {
          if (!active) return;
          setStatus(nextStatus);
          setEngine(nextEngine);
          setHAATCalculations(nextHAAT);
          setSnapshots(nextSnapshots);
          setAnalyses(nextAnalyses);
        },
      )
      .catch((loadError: unknown) => {
        if (active) {
          setError(
            errorMessage(
              loadError,
              "Unable to load directional analysis data.",
            ),
          );
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [incident]);

  async function refreshAnalyses() {
    if (!incident) return;
    setAnalyses(await listDirectionalCoverageAnalyses(incident.id));
    window.dispatchEvent(new Event("ict-directional-analyses-updated"));
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!incident || !canEdit) return;
    const data = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      await createDirectionalCoverageAnalysis({
        haat_calculation: String(data.get("haat_calculation")),
        subscriber_rf_input_snapshot: String(
          data.get("subscriber_rf_input_snapshot"),
        ),
        environment: String(
          data.get("environment"),
        ) as DirectionalCoverageAnalysis["environment"],
        preset: String(data.get("preset")),
      });
      await refreshAnalyses();
    } catch (submitError) {
      setError(
        errorMessage(
          submitError,
          "Unable to create directional coverage analysis.",
        ),
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleApprove(analysis: DirectionalCoverageAnalysis) {
    if (!canApprove || analysis.calculation_state !== "complete") return;
    if (
      !window.confirm(
        "Approve and lock these talk-out, talk-in, and probable two-way results with their exact evidence?",
      )
    ) {
      return;
    }
    setBusy(true);
    setError("");
    try {
      await approveDirectionalCoverageAnalysis(analysis.id);
      await refreshAnalyses();
    } catch (approvalError) {
      setError(
        errorMessage(
          approvalError,
          "Unable to approve directional coverage analysis.",
        ),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="coverage-panel" aria-labelledby="directional-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Asymmetric path decision support</p>
          <h2 id="directional-heading">
            Talk-out, talk-in, and two-way analysis
          </h2>
        </div>
        <span className="count">{analyses.length}</span>
      </div>
      <p className="panel-intro">
        Compare infrastructure-to-subscriber talk-out with
        subscriber-to-infrastructure talk-in. Probable two-way operation is the
        smaller supported nominal path—not a coverage guarantee, coordination
        decision, or spectrum authorization.
      </p>

      {!incident ? (
        <p className="empty">Select an incident to review directional paths.</p>
      ) : loading ? (
        <p role="status" aria-live="polite">
          Loading directional analysis…
        </p>
      ) : (
        <>
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}

          {status && (
            <article className="coverage-engine-card">
              <div>
                <strong>{status.rule_version}</strong>
                <span>
                  {status.approved_for_operational_use
                    ? "Approved directional rule"
                    : "Provisional directional rule—practitioner review required"}
                </span>
              </div>
              <p>{status.rule}</p>
              <p>{status.disclaimer}</p>
            </article>
          )}

          {canEdit && (
            <form className="coverage-form" onSubmit={handleCreate}>
              <h3>New directional analysis</h3>
              <p className="form-note">
                The HAAT record supplies the fixed infrastructure path. Select a
                separate approved portable, mobile, fixed, cache, gateway, or
                configurable subscriber snapshot for the unequal return path.
              </p>
              <label>
                Approved infrastructure HAAT
                <select
                  name="haat_calculation"
                  required
                  disabled={approvedHAAT.length === 0}
                >
                  <option value="">Select infrastructure evidence</option>
                  {approvedHAAT.map((calculation) => (
                    <option key={calculation.id} value={calculation.id}>
                      {calculation.site_name} · {calculation.rf_input_label} ·
                      HAAT {calculation.haat_m} m
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Approved subscriber input
                <select
                  name="subscriber_rf_input_snapshot"
                  required
                  disabled={snapshots.length === 0}
                >
                  <option value="">Select subscriber evidence</option>
                  {snapshots.map((snapshot) => (
                    <option key={snapshot.id} value={snapshot.id}>
                      {snapshot.profile_name} ·{" "}
                      {readable(snapshot.profile_type)} · version{" "}
                      {snapshot.profile_version_number} · {snapshot.label}
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
                  snapshots.length === 0 ||
                  Object.keys(engine?.presets ?? {}).length === 0
                }
              >
                Calculate separate paths
              </button>
            </form>
          )}

          <div className="coverage-results">
            <h3>Directional analysis history</h3>
            {analyses.length === 0 ? (
              <p className="empty">No directional analyses exist.</p>
            ) : (
              <div
                className="table-scroll"
                role="region"
                aria-label="Directional coverage analysis table"
              >
                <table>
                  <caption>
                    Separate nominal path results and probable two-way overlap;
                    manual rings and earlier single-path estimates remain
                    separate.
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Site / subscriber</th>
                      <th scope="col">Talk-out</th>
                      <th scope="col">Talk-in</th>
                      <th scope="col">Probable two-way</th>
                      <th scope="col">Limiting path</th>
                      <th scope="col">State</th>
                      <th scope="col">Evidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {analyses.map((analysis) => (
                      <tr key={analysis.id}>
                        <th scope="row">
                          {analysis.site_name}
                          <small>
                            {analysis.subscriber_profile_name} ·{" "}
                            {readable(analysis.subscriber_profile_type)}
                          </small>
                        </th>
                        <td>{distance(analysis.talk_out_distance_m)}</td>
                        <td>{distance(analysis.talk_in_distance_m)}</td>
                        <td>
                          {distance(analysis.probable_two_way_distance_m)}
                        </td>
                        <td>{readable(analysis.limiting_path)}</td>
                        <td>
                          {readable(analysis.calculation_state)} ·{" "}
                          {analysis.status}
                        </td>
                        <td>
                          <details>
                            <summary>Explanation and digests</summary>
                            <p>{analysis.explanation}</p>
                            {analysis.warnings.map((warning) => (
                              <p className="warning-text" key={warning}>
                                {warning}
                              </p>
                            ))}
                            {analysis.exclusions.map((exclusion) => (
                              <p
                                className="warning-text"
                                key={`${exclusion.code}-${exclusion.reason}`}
                              >
                                {exclusion.code}: {exclusion.reason}
                              </p>
                            ))}
                            <dl className="digest-list">
                              <div>
                                <dt>Engine</dt>
                                <dd>{analysis.engine_version}</dd>
                              </div>
                              <div>
                                <dt>Preset</dt>
                                <dd>{analysis.preset_version}</dd>
                              </div>
                              <div>
                                <dt>Two-way rule</dt>
                                <dd>{analysis.rule_version}</dd>
                              </div>
                              <div>
                                <dt>Input digest</dt>
                                <dd>{analysis.input_sha256}</dd>
                              </div>
                              <div>
                                <dt>Result digest</dt>
                                <dd>{analysis.result_sha256}</dd>
                              </div>
                            </dl>
                            {canApprove &&
                              analysis.status === "draft" &&
                              analysis.calculation_state === "complete" &&
                              configurationApproved(
                                status,
                                engine,
                                analysis,
                              ) && (
                                <button
                                  type="button"
                                  disabled={busy}
                                  onClick={() => void handleApprove(analysis)}
                                >
                                  Approve and lock directional analysis
                                </button>
                              )}
                            {canApprove &&
                              analysis.status === "draft" &&
                              analysis.calculation_state === "complete" &&
                              !configurationApproved(
                                status,
                                engine,
                                analysis,
                              ) && (
                                <p className="warning-text">
                                  The exact engine, preset, and two-way rule
                                  have not all passed their configured
                                  practitioner gates. Draft evidence remains
                                  reviewable but cannot be approved.
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
