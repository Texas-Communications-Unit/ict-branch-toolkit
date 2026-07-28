import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  approveTerrainAnalysis,
  cancelTerrainAnalysis,
  createTerrainAnalysis,
  getTerrainAnalysisStatus,
  listCoverageEstimates,
  listTerrainAnalyses,
  retryTerrainAnalysis,
  runTerrainAnalysis,
} from "./api";
import type {
  CoverageEstimate,
  Incident,
  TerrainAnalysis,
  TerrainAnalysisResult,
  TerrainAnalysisStatus,
  TerrainProfileSample,
} from "./types";

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

function shortDigest(value: string): string {
  return value ? `${value.slice(0, 12)}…` : "—";
}

function displayDistance(value: number | null | undefined): string {
  return value === null || value === undefined
    ? "Unsupported"
    : `${value.toLocaleString()} m`;
}

function sampleLabel(sample: TerrainProfileSample): string {
  if (sample.state !== "complete") return sample.state.replaceAll("_", " ");
  if (sample.visible === false) return "obstructed";
  if (sample.visible === true) return "clear";
  return "sampled";
}

function resultFor(analysis: TerrainAnalysis): TerrainAnalysisResult {
  return analysis.result_snapshot ?? {};
}

export function TerrainAnalysisWorkspace({
  incident,
}: {
  incident?: Incident;
}) {
  const [capability, setCapability] = useState<TerrainAnalysisStatus | null>(
    null,
  );
  const [coverage, setCoverage] = useState<CoverageEstimate[]>([]);
  const [analyses, setAnalyses] = useState<TerrainAnalysis[]>([]);
  const [analysisPage, setAnalysisPage] = useState(1);
  const [analysisCount, setAnalysisCount] = useState(0);
  const [hasNextPage, setHasNextPage] = useState(false);
  const [hasPreviousPage, setHasPreviousPage] = useState(false);
  const [expandedProfiles, setExpandedProfiles] = useState<
    Record<string, boolean>
  >({});
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const approvedCoverage = useMemo(
    () =>
      coverage.filter(
        (item) =>
          item.status === "approved" && item.calculation_state === "complete",
      ),
    [coverage],
  );
  const canEdit = Boolean(incident?.permissions.includes("rf.edit"));
  const canApprove = Boolean(incident?.permissions.includes("rf.approve"));

  const refresh = useCallback(async () => {
    if (!incident) {
      setCoverage([]);
      setAnalyses([]);
      setAnalysisCount(0);
      setHasNextPage(false);
      setHasPreviousPage(false);
      return;
    }
    setLoading(true);
    try {
      const [nextCapability, nextCoverage, nextAnalyses] = await Promise.all([
        getTerrainAnalysisStatus(),
        listCoverageEstimates(incident.id),
        listTerrainAnalyses(incident.id, analysisPage),
      ]);
      if (!nextCapability.provider || !nextCapability.engine) {
        throw new Error("The terrain capability response was incomplete.");
      }
      setCapability(nextCapability);
      setCoverage(nextCoverage);
      setAnalyses(nextAnalyses.results);
      setAnalysisCount(nextAnalyses.count);
      setHasNextPage(Boolean(nextAnalyses.next));
      setHasPreviousPage(Boolean(nextAnalyses.previous));
      setError("");
    } catch (caught) {
      setError(errorMessage(caught, "Unable to load terrain analysis."));
    } finally {
      setLoading(false);
    }
  }, [analysisPage, incident]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    setAnalysisPage(1);
    setExpandedProfiles({});
  }, [incident?.id]);

  async function handleQueue(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusyId("queue");
    setMessage("Queueing immutable terrain source evidence…");
    setError("");
    try {
      await createTerrainAnalysis({
        coverage_estimate: String(data.get("coverage_estimate")),
        azimuth_deg: String(data.get("azimuth_deg")),
        maximum_distance_m: Number(data.get("maximum_distance_m")),
        sample_interval_m: Number(data.get("sample_interval_m")),
        receiver_height_m: String(data.get("receiver_height_m")),
        clearance_m: String(data.get("clearance_m")),
      });
      setMessage("Terrain analysis queued. Review the inputs, then run it.");
      if (analysisPage === 1) {
        await refresh();
      } else {
        setAnalysisPage(1);
      }
    } catch (caught) {
      setMessage("");
      setError(errorMessage(caught, "Unable to queue terrain analysis."));
    } finally {
      setBusyId("");
    }
  }

  async function performAction(
    analysis: TerrainAnalysis,
    label: string,
    action: (id: string) => Promise<unknown>,
    moveToFirstPage = false,
  ) {
    setBusyId(analysis.id);
    setMessage(label);
    setError("");
    try {
      await action(analysis.id);
      setMessage(`${label.replace(/…$/, "")} complete.`);
      if (moveToFirstPage && analysisPage !== 1) {
        setAnalysisPage(1);
      } else {
        await refresh();
      }
    } catch (caught) {
      setMessage("");
      setError(errorMessage(caught, "The terrain action failed."));
    } finally {
      setBusyId("");
    }
  }

  return (
    <section className="coverage-panel" aria-labelledby="terrain-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Optional source-aware terrain evidence</p>
          <h2 id="terrain-heading">Terrain profile analysis</h2>
        </div>
        <span className="count">{analysisCount}</span>
      </div>
      <p className="disclaimer">
        Terrain results are a separate planning comparison. They never replace
        Phase 2 estimates and are not coverage guarantees, regulatory studies,
        coordination decisions, or field validation.
      </p>

      {!incident ? (
        <p className="empty">
          Select an incident to review terrain capability.
        </p>
      ) : loading && !capability ? (
        <p role="status" aria-live="polite">
          Loading terrain capability…
        </p>
      ) : (
        <>
          {capability && (
            <article className="coverage-engine-card">
              <div className="section-heading">
                <h3>Provider and method capability</h3>
                <span className="state-badges">
                  <span className="count">
                    {capability.available ? "available" : "fail closed"}
                  </span>
                  <span className="count">{capability.classification}</span>
                </span>
              </div>
              <dl className="evidence-list">
                <div>
                  <dt>Dataset</dt>
                  <dd>
                    {capability.provider.dataset_product} ·{" "}
                    {capability.provider.dataset_version || "not configured"}
                  </dd>
                </div>
                <div>
                  <dt>Resolution and datum</dt>
                  <dd>
                    {capability.provider.resolution_m
                      ? `${capability.provider.resolution_m} m`
                      : "not declared"}
                    {" · "}
                    {capability.provider.vertical_crs} →{" "}
                    {capability.provider.target_vertical_crs}
                  </dd>
                </div>
                <div>
                  <dt>Provider approval</dt>
                  <dd>
                    {capability.configured ? "configured" : "not configured"} ·{" "}
                    {capability.approved_for_analysis
                      ? "exact source and engine allowlisted"
                      : "qualified GIS/RF gate closed"}
                  </dd>
                </div>
                <div>
                  <dt>Method</dt>
                  <dd>
                    {capability.engine.method} ·{" "}
                    {capability.engine.engine_version}
                  </dd>
                </div>
                <div>
                  <dt>Supported model features</dt>
                  <dd>
                    sampled line of sight:{" "}
                    {capability.engine.capabilities.sampled_line_of_sight
                      ? "yes"
                      : "no"}
                    {" · "}diffraction:{" "}
                    {capability.engine.capabilities.diffraction ? "yes" : "no"}
                    {" · "}clutter:{" "}
                    {capability.engine.capabilities.clutter ? "yes" : "no"}
                  </dd>
                </div>
                <div>
                  <dt>Resource limits</dt>
                  <dd>
                    {capability.resource_safety_limits.maximum_distance_m.toLocaleString()}{" "}
                    m · {capability.resource_safety_limits.maximum_samples}{" "}
                    samples
                  </dd>
                </div>
              </dl>
              {capability.warning && (
                <p className="error-banner" role="status">
                  {capability.warning} Core planning remains available.
                </p>
              )}
              <p>{capability.cancellation_boundary}</p>
              <p className="disclaimer">{capability.disclaimer}</p>
            </article>
          )}

          {canEdit && (
            <form className="coverage-form terrain-form" onSubmit={handleQueue}>
              <h3>Queue a version-pinned terrain profile</h3>
              <p className="form-note">
                Choose an approved Phase 2 estimate, an explicit direction, and
                bounded sampling parameters. The selected provider, dataset,
                transformation, method, parameters, and digests are retained.
              </p>
              <label>
                Approved Phase 2 coverage estimate
                <select name="coverage_estimate" required>
                  <option value="">Select coverage estimate</option>
                  {approvedCoverage.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.site_name} · {item.environment} · nominal{" "}
                      {displayDistance(item.nominal_distance_m)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Azimuth (degrees)
                <input
                  name="azimuth_deg"
                  type="number"
                  min="0"
                  max="359.999"
                  step="0.001"
                  defaultValue="0"
                  required
                />
              </label>
              <label>
                Maximum profile distance (m)
                <input
                  name="maximum_distance_m"
                  type="number"
                  min="1"
                  max={
                    capability?.resource_safety_limits.maximum_distance_m ??
                    200000
                  }
                  defaultValue="10000"
                  required
                />
              </label>
              <label>
                Sample interval (m)
                <input
                  name="sample_interval_m"
                  type="number"
                  min="1"
                  max="100000"
                  defaultValue="100"
                  required
                />
              </label>
              <label>
                Receiver height above terrain (m)
                <input
                  name="receiver_height_m"
                  type="number"
                  min="0"
                  max="1000"
                  step="0.001"
                  defaultValue="1.5"
                  required
                />
              </label>
              <label>
                Additional obstruction clearance (m)
                <input
                  name="clearance_m"
                  type="number"
                  min="0"
                  max="1000"
                  step="0.001"
                  defaultValue="0"
                  required
                />
              </label>
              <button
                type="submit"
                disabled={
                  busyId === "queue" ||
                  !capability?.available ||
                  approvedCoverage.length === 0
                }
                title={
                  capability?.available
                    ? "Queue this exact terrain profile request"
                    : "A qualified, allowlisted terrain configuration is required"
                }
              >
                Queue terrain profile
              </button>
            </form>
          )}

          {message && (
            <p role="status" aria-live="polite">
              {message}
            </p>
          )}
          {error && (
            <p className="error-banner" role="alert">
              {error}
            </p>
          )}

          <div className="coverage-results">
            <div className="section-heading">
              <h3>Terrain evidence history</h3>
              <div className="button-row">
                <button
                  type="button"
                  onClick={() => setAnalysisPage((page) => page - 1)}
                  disabled={loading || !hasPreviousPage}
                >
                  Previous terrain page
                </button>
                <span>
                  Page {analysisPage} · {analysisCount} retained
                </span>
                <button
                  type="button"
                  onClick={() => setAnalysisPage((page) => page + 1)}
                  disabled={loading || !hasNextPage}
                >
                  Next terrain page
                </button>
                <button
                  type="button"
                  onClick={() => void refresh()}
                  disabled={loading}
                >
                  Refresh status
                </button>
              </div>
            </div>
            {analyses.length === 0 ? (
              <p className="empty">No terrain analysis has been queued.</p>
            ) : (
              <div className="resource-grid terrain-results">
                {analyses.map((analysis) => {
                  const result = resultFor(analysis);
                  const profile = result.profile;
                  const comparison = result.comparison;
                  const lineOfSight = result.line_of_sight;
                  const samples = profile?.samples ?? [];
                  return (
                    <article key={analysis.id} className="coverage-engine-card">
                      <div className="section-heading">
                        <h4>
                          {analysis.dataset_product} · {analysis.azimuth_deg}°
                        </h4>
                        <span className="state-badges">
                          <span className="count">{analysis.job_state}</span>
                          {analysis.analysis_state && (
                            <span className="count">
                              {analysis.analysis_state}
                            </span>
                          )}
                        </span>
                      </div>
                      <div
                        role="progressbar"
                        aria-label={`Terrain analysis progress for ${analysis.id}`}
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-valuenow={analysis.progress_percent}
                      >
                        <progress value={analysis.progress_percent} max={100}>
                          {analysis.progress_percent}%
                        </progress>
                      </div>
                      <dl className="evidence-list">
                        <div>
                          <dt>Review state</dt>
                          <dd>
                            {analysis.status}
                            {analysis.is_stale ? " · stale" : " · current"}
                          </dd>
                        </div>
                        <div>
                          <dt>Provider / dataset</dt>
                          <dd>
                            {analysis.provider} {analysis.provider_version} ·{" "}
                            {analysis.dataset_version}
                          </dd>
                        </div>
                        <div>
                          <dt>Method / application</dt>
                          <dd>
                            {analysis.engine_version} · {analysis.app_version}
                          </dd>
                        </div>
                        <div>
                          <dt>Input / result digests</dt>
                          <dd>
                            <code>{shortDigest(analysis.input_sha256)}</code>
                            {" / "}
                            <code>{shortDigest(analysis.result_sha256)}</code>
                          </dd>
                        </div>
                      </dl>

                      {analysis.failure_message && (
                        <p className="error-banner" role="alert">
                          <strong>{analysis.failure_code}:</strong>{" "}
                          {analysis.failure_message}
                        </p>
                      )}
                      {analysis.is_stale && (
                        <p className="error-banner" role="alert">
                          <strong>Stale retained evidence:</strong>{" "}
                          {analysis.stale_reasons.join(", ")}. Queue new work
                          from the current approved configuration.
                        </p>
                      )}

                      {analysis.job_state === "complete" && (
                        <>
                          <h5>Phase 2 and terrain comparison</h5>
                          <div className="terrain-comparison">
                            <div>
                              <strong>Phase 2 nominal estimate</strong>
                              <span>
                                {displayDistance(
                                  comparison?.phase2_nominal_distance_m,
                                )}
                              </span>
                              <small>
                                Coarse prior layer; retained unchanged
                              </small>
                            </div>
                            <div>
                              <strong>Terrain continuous clear path</strong>
                              <span>
                                {displayDistance(
                                  comparison?.terrain_continuous_los_distance_m,
                                )}
                              </span>
                              <small>
                                {analysis.analysis_state === "unsupported"
                                  ? "Unsupported profile"
                                  : `${lineOfSight?.obstruction_count ?? 0} obstructions · ${profile?.gap_count ?? 0} gaps`}
                              </small>
                            </div>
                          </div>
                          {comparison?.interpretation && (
                            <p>{comparison.interpretation}</p>
                          )}
                          {comparison?.materially_different === true && (
                            <p className="error-banner" role="alert">
                              Material difference detected. Qualified review is
                              required; neither layer is silently replaced.
                            </p>
                          )}
                          {result.explanation && <p>{result.explanation}</p>}
                          {(result.warnings?.length ?? 0) > 0 && (
                            <details>
                              <summary>
                                Warnings ({result.warnings?.length})
                              </summary>
                              <ul>
                                {result.warnings?.map((warning) => (
                                  <li key={warning}>{warning}</li>
                                ))}
                              </ul>
                            </details>
                          )}
                          <details
                            onToggle={(event) => {
                              const open = event.currentTarget.open;
                              setExpandedProfiles((current) => ({
                                ...current,
                                [analysis.id]: open,
                              }));
                            }}
                          >
                            <summary>
                              Accessible terrain profile ({samples.length}{" "}
                              samples)
                            </summary>
                            {!expandedProfiles[
                              analysis.id
                            ] ? null : samples.length === 0 ? (
                              <p>No profile samples were returned.</p>
                            ) : (
                              <div className="table-scroll">
                                <table className="data-table">
                                  <caption>
                                    Distinct states identify clear, obstructed,
                                    missing, and out-of-coverage samples without
                                    relying on a map or color.
                                  </caption>
                                  <thead>
                                    <tr>
                                      <th scope="col">Distance</th>
                                      <th scope="col">Terrain</th>
                                      <th scope="col">Path state</th>
                                      <th scope="col">Location</th>
                                      <th scope="col">Reason</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {samples.map((sample) => (
                                      <tr
                                        key={`${analysis.id}-${sample.distance_m}`}
                                        data-path-state={sampleLabel(sample)}
                                      >
                                        <td>{sample.distance_m} m</td>
                                        <td>
                                          {sample.terrain_elevation_m
                                            ? `${sample.terrain_elevation_m} m`
                                            : "not available"}
                                        </td>
                                        <td>
                                          <strong>{sampleLabel(sample)}</strong>
                                        </td>
                                        <td>
                                          {sample.latitude}, {sample.longitude}
                                        </td>
                                        <td>{sample.reason || "—"}</td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            )}
                          </details>
                        </>
                      )}

                      <div className="button-row">
                        {canEdit && analysis.job_state === "queued" && (
                          <>
                            <button
                              type="button"
                              disabled={busyId === analysis.id}
                              onClick={() =>
                                void performAction(
                                  analysis,
                                  "Running bounded terrain analysis…",
                                  runTerrainAnalysis,
                                )
                              }
                            >
                              Run terrain analysis
                            </button>
                            <button
                              type="button"
                              disabled={busyId === analysis.id}
                              onClick={() =>
                                void performAction(
                                  analysis,
                                  "Cancelling queued terrain work…",
                                  cancelTerrainAnalysis,
                                )
                              }
                            >
                              Cancel queued run
                            </button>
                          </>
                        )}
                        {canEdit &&
                          ["failed", "cancelled"].includes(
                            analysis.job_state,
                          ) && (
                            <button
                              type="button"
                              disabled={busyId === analysis.id}
                              onClick={() =>
                                void performAction(
                                  analysis,
                                  "Queueing retained terrain retry…",
                                  retryTerrainAnalysis,
                                  true,
                                )
                              }
                            >
                              Queue retry
                            </button>
                          )}
                        {canApprove &&
                          analysis.job_state === "complete" &&
                          analysis.status === "draft" && (
                            <button
                              type="button"
                              disabled={
                                busyId === analysis.id ||
                                !analysis.approval_eligible
                              }
                              title={
                                analysis.approval_eligible
                                  ? "Approve this exact complete terrain result"
                                  : "Only current, complete terrain evidence can be approved"
                              }
                              onClick={() =>
                                void performAction(
                                  analysis,
                                  "Approving exact terrain evidence…",
                                  approveTerrainAnalysis,
                                )
                              }
                            >
                              Approve terrain evidence
                            </button>
                          )}
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </div>
        </>
      )}
    </section>
  );
}
