import { type FormEvent, useEffect, useMemo, useState } from "react";

import {
  approveCalibrationSet,
  createCalibrationSet,
  createFieldObservation,
  getCalibrationStatus,
  listCalibrationSets,
  listCoverageEstimates,
  listDirectionalCoverageAnalyses,
  listFieldObservations,
  listRFAnalysisInputSnapshots,
  reviewFieldObservation,
} from "./api";
import type {
  CalibrationSet,
  CalibrationStatus,
  CoverageEstimate,
  DirectionalCoverageAnalysis,
  FieldObservation,
  Incident,
  RFAnalysisInputSnapshot,
} from "./types";

const qualityFlagOptions = [
  "equipment_uncertain",
  "interference_observed",
  "location_uncertain",
  "missing_measurement",
  "multipath_suspected",
  "obstruction_observed",
  "outlier_candidate",
  "weather_effect",
] as const;

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

function readable(value: string): string {
  return value.replaceAll("_", " ");
}

function localDateTimeValue(): string {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function metric(value: string | undefined): string {
  return value === undefined ? "Not available" : Number(value).toFixed(1);
}

export function FieldCalibrationWorkspace({
  incident,
}: {
  incident?: Incident;
}) {
  const [status, setStatus] = useState<CalibrationStatus | null>(null);
  const [snapshots, setSnapshots] = useState<RFAnalysisInputSnapshot[]>([]);
  const [coverageEstimates, setCoverageEstimates] = useState<
    CoverageEstimate[]
  >([]);
  const [directionalAnalyses, setDirectionalAnalyses] = useState<
    DirectionalCoverageAnalysis[]
  >([]);
  const [observations, setObservations] = useState<FieldObservation[]>([]);
  const [calibrationSets, setCalibrationSets] = useState<CalibrationSet[]>([]);
  const [selectedObservations, setSelectedObservations] = useState<string[]>(
    [],
  );
  const [supersedes, setSupersedes] = useState("");
  const [locationPrecision, setLocationPrecision] =
    useState<FieldObservation["location_precision"]>("generalized");
  const [evidenceType, setEvidenceType] =
    useState<FieldObservation["evidence_type"]>("measured");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const canEdit = incident?.permissions.includes("rf.edit") ?? false;
  const canApprove = incident?.permissions.includes("rf.approve") ?? false;
  const activeSnapshots = useMemo(
    () => snapshots.filter((snapshot) => !snapshot.archived_at),
    [snapshots],
  );
  const approvedCoverage = useMemo(
    () =>
      coverageEstimates.filter(
        (estimate) =>
          estimate.status === "approved" &&
          estimate.calculation_state === "complete",
      ),
    [coverageEstimates],
  );
  const approvedDirectional = useMemo(
    () =>
      directionalAnalyses.filter(
        (analysis) =>
          analysis.status === "approved" &&
          analysis.calculation_state === "complete",
      ),
    [directionalAnalyses],
  );
  const eligibleObservations = useMemo(
    () =>
      observations.filter(
        (observation) =>
          observation.current_review_state === "approved" &&
          observation.superseded_by === null,
      ),
    [observations],
  );

  useEffect(() => {
    let active = true;
    if (!incident) {
      setStatus(null);
      setSnapshots([]);
      setCoverageEstimates([]);
      setDirectionalAnalyses([]);
      setObservations([]);
      setCalibrationSets([]);
      setSelectedObservations([]);
      setError("");
      return;
    }
    setLoading(true);
    setError("");
    Promise.all([
      getCalibrationStatus(),
      listRFAnalysisInputSnapshots(incident.id),
      listCoverageEstimates(incident.id),
      listDirectionalCoverageAnalyses(incident.id),
      listFieldObservations(incident.id),
      listCalibrationSets(incident.id),
    ])
      .then(
        ([
          nextStatus,
          nextSnapshots,
          nextCoverage,
          nextDirectional,
          nextObservations,
          nextCalibrationSets,
        ]) => {
          if (!active) return;
          setStatus(nextStatus);
          setSnapshots(nextSnapshots);
          setCoverageEstimates(nextCoverage);
          setDirectionalAnalyses(nextDirectional);
          setObservations(nextObservations);
          setCalibrationSets(nextCalibrationSets);
        },
      )
      .catch((loadError: unknown) => {
        if (active) {
          setError(
            errorMessage(
              loadError,
              "Unable to load field observation and calibration data.",
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

  async function refreshOperationalData() {
    if (!incident) return;
    const [nextObservations, nextCalibrationSets] = await Promise.all([
      listFieldObservations(incident.id),
      listCalibrationSets(incident.id),
    ]);
    setObservations(nextObservations);
    setCalibrationSets(nextCalibrationSets);
    setSelectedObservations((current) =>
      current.filter((id) =>
        nextObservations.some(
          (observation) =>
            observation.id === id &&
            observation.current_review_state === "approved" &&
            observation.superseded_by === null,
        ),
      ),
    );
  }

  async function handleObservation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!incident || !canEdit) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    const qualityFlags = qualityFlagOptions.filter(
      (flag) => data.get(`quality_${flag}`) === "on",
    );
    const environment = Object.fromEntries(
      ["terrain", "weather", "structures", "vegetation", "mobility"]
        .map((key) => [key, String(data.get(key) ?? "").trim()])
        .filter(([, value]) => value),
    );
    const measurements = Object.fromEntries(
      [
        "measured_distance_m",
        "predicted_distance_m",
        "rssi_dbm",
        "signal_quality_percent",
      ]
        .map((key) => [key, String(data.get(key) ?? "").trim()])
        .filter(([, value]) => value),
    );
    setBusy(true);
    setError("");
    try {
      await createFieldObservation({
        incident: incident.id,
        infrastructure_rf_input_snapshot: String(
          data.get("infrastructure_rf_input_snapshot"),
        ),
        subscriber_rf_input_snapshot: String(
          data.get("subscriber_rf_input_snapshot"),
        ),
        coverage_estimate: String(data.get("coverage_estimate") || "") || null,
        directional_analysis:
          String(data.get("directional_analysis") || "") || null,
        supersedes: supersedes || null,
        classification: String(
          data.get("classification"),
        ) as FieldObservation["classification"],
        evidence_type: evidenceType,
        observed_from: new Date(
          String(data.get("observed_from")),
        ).toISOString(),
        observed_to: new Date(String(data.get("observed_to"))).toISOString(),
        location_precision: locationPrecision,
        latitude:
          locationPrecision === "redacted"
            ? null
            : String(data.get("latitude")),
        longitude:
          locationPrecision === "redacted"
            ? null
            : String(data.get("longitude")),
        location_precision_m:
          locationPrecision === "redacted"
            ? null
            : Number(data.get("location_precision_m")),
        direction_degrees: String(data.get("direction_degrees") || "") || null,
        path_distance_m: data.get("path_distance_m")
          ? Number(data.get("path_distance_m"))
          : null,
        observer_source: String(data.get("observer_source")),
        collection_method: String(data.get("collection_method")),
        environment,
        measurements,
        notes: String(data.get("notes") || ""),
        quality_flags: qualityFlags,
        source_record_id: String(data.get("source_record_id") || ""),
        source_revision: String(data.get("source_revision")),
      });
      form.reset();
      setSupersedes("");
      setLocationPrecision("generalized");
      setEvidenceType("measured");
      await refreshOperationalData();
    } catch (submitError) {
      setError(
        errorMessage(submitError, "Unable to record the field observation."),
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleReview(
    observation: FieldObservation,
    decision: "approved" | "excluded",
  ) {
    if (!canApprove) return;
    const reason = window.prompt(
      `Record the reason this observation is ${decision}. The decision is append-only.`,
    );
    if (!reason?.trim()) return;
    setBusy(true);
    setError("");
    try {
      await reviewFieldObservation(observation.id, decision, reason.trim());
      await refreshOperationalData();
    } catch (reviewError) {
      setError(errorMessage(reviewError, "Unable to record the review."));
    } finally {
      setBusy(false);
    }
  }

  function toggleObservation(id: string) {
    setSelectedObservations((current) =>
      current.includes(id)
        ? current.filter((candidate) => candidate !== id)
        : [...current, id],
    );
  }

  async function handleCalibration(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!incident || !canEdit) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true);
    setError("");
    try {
      await createCalibrationSet({
        incident: incident.id,
        name: String(data.get("name")),
        observations: selectedObservations,
        baseline_preset: String(data.get("baseline_preset")),
        baseline_preset_version: String(data.get("baseline_preset_version")),
        parameters: {
          minimum_samples: Number(data.get("minimum_samples")),
          minimum_ratio: String(data.get("minimum_ratio")),
          maximum_ratio: String(data.get("maximum_ratio")),
        },
      });
      setSelectedObservations([]);
      await refreshOperationalData();
    } catch (calibrationError) {
      setError(
        errorMessage(calibrationError, "Unable to create the calibration set."),
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleApprove(calibrationSet: CalibrationSet) {
    if (!canApprove || calibrationSet.calculation_state !== "complete") return;
    if (
      !window.confirm(
        "Approve and lock this incident-local calibration evidence? This does not promote it to an organization default.",
      )
    ) {
      return;
    }
    setBusy(true);
    setError("");
    try {
      await approveCalibrationSet(calibrationSet.id);
      await refreshOperationalData();
    } catch (approvalError) {
      setError(
        errorMessage(approvalError, "Unable to approve the calibration set."),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="coverage-panel" aria-labelledby="calibration-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Controlled field evidence</p>
          <h2 id="calibration-heading">
            Field observations and local calibration
          </h2>
        </div>
        <span className="count">{observations.length}</span>
      </div>
      <p className="panel-intro">
        Record synthetic good, marginal, and failed-communications evidence,
        review it without rewriting history, and compare an incident-local
        fitted recommendation with its baseline. This does not authorize
        communications use or replace practitioner judgment.
      </p>

      {!incident ? (
        <p className="empty">
          Select an incident to review observations and calibration sets.
        </p>
      ) : loading ? (
        <p role="status" aria-live="polite">
          Loading field evidence…
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
                <strong>{status.algorithm_version}</strong>
                <span>
                  {status.approved_for_operational_use
                    ? "Configured practitioner gate passed"
                    : "Provisional method—RF/privacy review required"}
                </span>
              </div>
              <p>{status.location_rule}</p>
              <p>{status.promotion_rule}</p>
              <p>{status.disclaimer}</p>
            </article>
          )}

          {canEdit && (
            <form className="coverage-form" onSubmit={handleObservation}>
              <div className="section-heading">
                <div>
                  <p className="eyebrow">Append-only evidence</p>
                  <h3>Record a field observation</h3>
                </div>
              </div>
              <p className="warning-text">
                Use synthetic data only. Generalized coordinates are rounded
                before storage; redacted coordinates are discarded.
              </p>
              <div className="form-grid">
                <label>
                  Infrastructure RF snapshot
                  <select
                    name="infrastructure_rf_input_snapshot"
                    required
                    disabled={activeSnapshots.length === 0}
                  >
                    <option value="">Select approved snapshot</option>
                    {activeSnapshots.map((snapshot) => (
                      <option key={snapshot.id} value={snapshot.id}>
                        {snapshot.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Subscriber RF snapshot
                  <select
                    name="subscriber_rf_input_snapshot"
                    required
                    disabled={activeSnapshots.length === 0}
                  >
                    <option value="">Select distinct snapshot</option>
                    {activeSnapshots.map((snapshot) => (
                      <option key={snapshot.id} value={snapshot.id}>
                        {snapshot.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Approved coverage estimate (optional)
                  <select name="coverage_estimate">
                    <option value="">No coverage estimate</option>
                    {approvedCoverage.map((estimate) => (
                      <option key={estimate.id} value={estimate.id}>
                        {estimate.site_name} · {estimate.preset_version}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Approved directional analysis (optional)
                  <select name="directional_analysis">
                    <option value="">No directional analysis</option>
                    {approvedDirectional.map((analysis) => (
                      <option key={analysis.id} value={analysis.id}>
                        {analysis.site_name} ·{" "}
                        {analysis.subscriber_profile_name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Classification
                  <select name="classification" defaultValue="good" required>
                    <option value="good">Good communications</option>
                    <option value="marginal">Marginal communications</option>
                    <option value="failed">Failed communications</option>
                  </select>
                </label>
                <label>
                  Evidence type
                  <select
                    name="evidence_type"
                    value={evidenceType}
                    onChange={(event) =>
                      setEvidenceType(
                        event.target.value as FieldObservation["evidence_type"],
                      )
                    }
                    required
                  >
                    <option value="measured">Measured value</option>
                    <option value="operator">Operator judgment</option>
                    <option value="imported">Imported record</option>
                    <option value="modeled">Modeled value</option>
                  </select>
                </label>
                <label>
                  Observed from
                  <input
                    name="observed_from"
                    type="datetime-local"
                    defaultValue={localDateTimeValue()}
                    required
                  />
                </label>
                <label>
                  Observed to
                  <input
                    name="observed_to"
                    type="datetime-local"
                    defaultValue={localDateTimeValue()}
                    required
                  />
                </label>
                <label>
                  Location handling
                  <select
                    name="location_precision"
                    value={locationPrecision}
                    onChange={(event) =>
                      setLocationPrecision(
                        event.target
                          .value as FieldObservation["location_precision"],
                      )
                    }
                    required
                  >
                    <option value="generalized">
                      Generalized before storage
                    </option>
                    <option value="redacted">Redacted before storage</option>
                    <option value="exact">Exact—sensitive</option>
                  </select>
                </label>
                {locationPrecision !== "redacted" && (
                  <>
                    <label>
                      Latitude (WGS 84)
                      <input
                        name="latitude"
                        type="number"
                        min="-90"
                        max="90"
                        step="0.000001"
                        required
                      />
                    </label>
                    <label>
                      Longitude (WGS 84)
                      <input
                        name="longitude"
                        type="number"
                        min="-180"
                        max="180"
                        step="0.000001"
                        required
                      />
                    </label>
                    <label>
                      Location precision (m)
                      <input
                        name="location_precision_m"
                        type="number"
                        min={locationPrecision === "generalized" ? 100 : 1}
                        max="1000000"
                        defaultValue={
                          locationPrecision === "generalized" ? 1000 : 10
                        }
                        required
                      />
                    </label>
                  </>
                )}
                <label>
                  Direction (degrees, optional)
                  <input
                    name="direction_degrees"
                    type="number"
                    min="0"
                    max="359.999"
                    step="0.001"
                  />
                </label>
                <label>
                  Path distance (m, optional)
                  <input
                    name="path_distance_m"
                    type="number"
                    min="1"
                    max="1000000"
                  />
                </label>
                <label>
                  Observer or source
                  <input
                    name="observer_source"
                    maxLength={160}
                    placeholder="Synthetic exercise team"
                    required
                  />
                </label>
                <label>
                  Collection method
                  <input
                    name="collection_method"
                    maxLength={120}
                    placeholder="Scripted field check"
                    required
                  />
                </label>
                <label>
                  Measured distance (m)
                  <input
                    name="measured_distance_m"
                    type="number"
                    min="0.001"
                    max="1000000"
                    step="0.001"
                  />
                </label>
                <label>
                  Predicted distance (m)
                  <input
                    name="predicted_distance_m"
                    type="number"
                    min="0.001"
                    max="1000000"
                    step="0.001"
                  />
                </label>
                <label>
                  RSSI (dBm, optional)
                  <input
                    name="rssi_dbm"
                    type="number"
                    min="-300"
                    max="100"
                    step="0.001"
                  />
                </label>
                <label>
                  Signal quality (%, optional)
                  <input
                    name="signal_quality_percent"
                    type="number"
                    min="0"
                    max="100"
                    step="0.001"
                  />
                </label>
                <label>
                  Terrain descriptor
                  <input name="terrain" maxLength={80} />
                </label>
                <label>
                  Weather descriptor
                  <input name="weather" maxLength={80} />
                </label>
                <label>
                  Structures descriptor
                  <input name="structures" maxLength={80} />
                </label>
                <label>
                  Vegetation descriptor
                  <input name="vegetation" maxLength={80} />
                </label>
                <label>
                  Mobility descriptor
                  <input name="mobility" maxLength={80} />
                </label>
                <label>
                  Source record ID
                  <input
                    name="source_record_id"
                    maxLength={160}
                    required={evidenceType === "imported"}
                  />
                </label>
                <label>
                  Source revision
                  <input
                    name="source_revision"
                    defaultValue="synthetic-observation-v1"
                    maxLength={160}
                    required
                  />
                </label>
                <label>
                  Corrects observation (optional)
                  <select
                    name="supersedes"
                    value={supersedes}
                    onChange={(event) => setSupersedes(event.target.value)}
                  >
                    <option value="">New observation</option>
                    {observations
                      .filter((observation) => !observation.superseded_by)
                      .map((observation) => (
                        <option key={observation.id} value={observation.id}>
                          {readable(observation.classification)} ·{" "}
                          {new Date(observation.observed_to).toLocaleString()}
                        </option>
                      ))}
                  </select>
                </label>
              </div>
              <fieldset>
                <legend>Quality flags</legend>
                <div className="checkbox-grid">
                  {qualityFlagOptions.map((flag) => (
                    <label key={flag}>
                      <input name={`quality_${flag}`} type="checkbox" />
                      {readable(flag)}
                    </label>
                  ))}
                </div>
              </fieldset>
              <label>
                Notes
                <textarea
                  name="notes"
                  rows={3}
                  maxLength={2000}
                  placeholder="Do not enter protected or operational details."
                />
              </label>
              <button
                type="submit"
                disabled={busy || activeSnapshots.length < 2}
              >
                Record immutable observation
              </button>
            </form>
          )}

          <div className="table-wrap">
            <table className="data-table">
              <caption>Field observation history</caption>
              <thead>
                <tr>
                  <th scope="col">Observation</th>
                  <th scope="col">Evidence</th>
                  <th scope="col">Location</th>
                  <th scope="col">Review</th>
                  <th scope="col">Provenance and actions</th>
                </tr>
              </thead>
              <tbody>
                {observations.length === 0 ? (
                  <tr>
                    <td colSpan={5}>No field observations are recorded.</td>
                  </tr>
                ) : (
                  observations.map((observation) => (
                    <tr key={observation.id}>
                      <th scope="row">
                        {readable(observation.classification)}
                        <small>
                          {new Date(observation.observed_to).toLocaleString()}
                        </small>
                      </th>
                      <td>
                        {readable(observation.evidence_type)}
                        <small>
                          {observation.measurements.measured_distance_m
                            ? `${observation.measurements.measured_distance_m} m measured`
                            : "No measured distance"}
                        </small>
                      </td>
                      <td>
                        {readable(observation.location_precision)}
                        <small>
                          {observation.latitude && observation.longitude
                            ? `${observation.latitude}, ${observation.longitude} · ${observation.location_precision_m} m`
                            : "Coordinates not retained"}
                        </small>
                      </td>
                      <td>
                        <span
                          className={`status ${observation.current_review_state}`}
                        >
                          {readable(observation.current_review_state)}
                        </span>
                        {observation.superseded_by && (
                          <small>Superseded by correction</small>
                        )}
                      </td>
                      <td>
                        <details>
                          <summary>Evidence</summary>
                          <dl className="evidence-list">
                            <div>
                              <dt>Input digest</dt>
                              <dd>{observation.input_sha256}</dd>
                            </div>
                            <div>
                              <dt>Source revision</dt>
                              <dd>{observation.source_revision}</dd>
                            </div>
                            <div>
                              <dt>Infrastructure</dt>
                              <dd>{observation.infrastructure_label}</dd>
                            </div>
                            <div>
                              <dt>Subscriber</dt>
                              <dd>{observation.subscriber_label}</dd>
                            </div>
                          </dl>
                        </details>
                        {canEdit && !observation.superseded_by && (
                          <button
                            type="button"
                            className="text-button"
                            onClick={() => setSupersedes(observation.id)}
                          >
                            Correct by supersession
                          </button>
                        )}
                        {canApprove && !observation.superseded_by && (
                          <div className="button-row">
                            {observation.current_review_state !==
                              "approved" && (
                              <button
                                type="button"
                                disabled={busy}
                                onClick={() =>
                                  void handleReview(observation, "approved")
                                }
                              >
                                Approve evidence
                              </button>
                            )}
                            {observation.current_review_state !==
                              "excluded" && (
                              <button
                                type="button"
                                className="secondary"
                                disabled={busy}
                                onClick={() =>
                                  void handleReview(observation, "excluded")
                                }
                              >
                                Exclude evidence
                              </button>
                            )}
                          </div>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {canEdit && (
            <form className="coverage-form" onSubmit={handleCalibration}>
              <div className="section-heading">
                <div>
                  <p className="eyebrow">Versioned comparison</p>
                  <h3>Create an incident-local calibration set</h3>
                </div>
                <span className="count">{selectedObservations.length}</span>
              </div>
              <p>
                Select currently approved observations. Missing distance pairs
                and ratios outside the declared bounds remain visible as
                exclusions.
              </p>
              <fieldset>
                <legend>Approved observations</legend>
                {eligibleObservations.length === 0 ? (
                  <p className="empty">
                    Approve observations before creating a calibration set.
                  </p>
                ) : (
                  <div className="checkbox-grid">
                    {eligibleObservations.map((observation) => (
                      <label key={observation.id}>
                        <input
                          type="checkbox"
                          checked={selectedObservations.includes(
                            observation.id,
                          )}
                          onChange={() => toggleObservation(observation.id)}
                        />
                        {readable(observation.classification)} ·{" "}
                        {observation.measurements.measured_distance_m ??
                          "missing"}{" "}
                        m measured /{" "}
                        {observation.measurements.predicted_distance_m ??
                          "missing"}{" "}
                        m predicted
                      </label>
                    ))}
                  </div>
                )}
              </fieldset>
              <div className="form-grid">
                <label>
                  Calibration name
                  <input
                    name="name"
                    defaultValue="Incident-local field calibration"
                    maxLength={160}
                    required
                  />
                </label>
                <label>
                  Baseline preset
                  <input
                    name="baseline_preset"
                    defaultValue="balanced"
                    required
                  />
                </label>
                <label>
                  Baseline preset version
                  <input
                    name="baseline_preset_version"
                    defaultValue="balanced-v1-provisional"
                    required
                  />
                </label>
                <label>
                  Minimum usable samples
                  <input
                    name="minimum_samples"
                    type="number"
                    min="3"
                    max="100"
                    defaultValue="3"
                    required
                  />
                </label>
                <label>
                  Minimum ratio
                  <input
                    name="minimum_ratio"
                    type="number"
                    min="0.01"
                    max="1"
                    step="0.001"
                    defaultValue="0.25"
                    required
                  />
                </label>
                <label>
                  Maximum ratio
                  <input
                    name="maximum_ratio"
                    type="number"
                    min="1"
                    max="10"
                    step="0.001"
                    defaultValue="4"
                    required
                  />
                </label>
              </div>
              <button
                type="submit"
                disabled={busy || selectedObservations.length === 0}
              >
                Calculate transparent comparison
              </button>
            </form>
          )}

          <div className="table-wrap">
            <table className="data-table">
              <caption>Calibration set history</caption>
              <thead>
                <tr>
                  <th scope="col">Set</th>
                  <th scope="col">Evidence</th>
                  <th scope="col">Recommendation</th>
                  <th scope="col">Before / after</th>
                  <th scope="col">Status and approval</th>
                </tr>
              </thead>
              <tbody>
                {calibrationSets.length === 0 ? (
                  <tr>
                    <td colSpan={5}>No calibration sets are recorded.</td>
                  </tr>
                ) : (
                  calibrationSets.map((calibrationSet) => (
                    <tr key={calibrationSet.id}>
                      <th scope="row">
                        {calibrationSet.name} v{calibrationSet.version}
                        <small>{calibrationSet.algorithm_version}</small>
                      </th>
                      <td>
                        {calibrationSet.observation_ids.length} selected
                        <small>
                          {calibrationSet.exclusions.length} excluded from fit
                        </small>
                      </td>
                      <td>
                        {calibrationSet.recommended_preset.distance_multiplier
                          ? `${calibrationSet.recommended_preset.distance_multiplier}× distance`
                          : "Not produced"}
                        <small>Incident-local · not promoted</small>
                      </td>
                      <td>
                        {calibrationSet.before_after.before &&
                        calibrationSet.before_after.after ? (
                          <>
                            MAE{" "}
                            {metric(
                              calibrationSet.before_after.before
                                .mean_absolute_error_m,
                            )}{" "}
                            m →{" "}
                            {metric(
                              calibrationSet.before_after.after
                                .mean_absolute_error_m,
                            )}{" "}
                            m
                            <small>
                              MAPE{" "}
                              {metric(
                                calibrationSet.before_after.before
                                  .mean_absolute_percentage_error,
                              )}
                              % →{" "}
                              {metric(
                                calibrationSet.before_after.after
                                  .mean_absolute_percentage_error,
                              )}
                              %
                            </small>
                          </>
                        ) : (
                          "Insufficient usable evidence"
                        )}
                      </td>
                      <td>
                        <span className={`status ${calibrationSet.status}`}>
                          {readable(calibrationSet.status)}
                        </span>
                        <small>
                          {readable(calibrationSet.calculation_state)}
                        </small>
                        <details>
                          <summary>Provenance and exclusions</summary>
                          <dl className="evidence-list">
                            <div>
                              <dt>Observation digest</dt>
                              <dd>{calibrationSet.observation_sha256}</dd>
                            </div>
                            <div>
                              <dt>Result digest</dt>
                              <dd>{calibrationSet.result_sha256}</dd>
                            </div>
                          </dl>
                          {calibrationSet.warnings.map((warning) => (
                            <p key={warning}>{warning}</p>
                          ))}
                          {calibrationSet.exclusions.map((exclusion) => (
                            <p
                              key={`${exclusion.observation_id}-${exclusion.code}`}
                            >
                              {readable(exclusion.code)}: {exclusion.reason}
                            </p>
                          ))}
                        </details>
                        {canApprove &&
                          status?.approved_for_operational_use &&
                          calibrationSet.status === "draft" &&
                          calibrationSet.calculation_state === "complete" && (
                            <button
                              type="button"
                              disabled={busy}
                              onClick={() => void handleApprove(calibrationSet)}
                            >
                              Approve and lock evidence
                            </button>
                          )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
