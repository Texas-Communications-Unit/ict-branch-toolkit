import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  approvePhase2ValidationBundle,
  cancelPhase2ValidationBundle,
  createPhase2ValidationBundle,
  downloadPhase2ValidationBundle,
  getPhase2ValidationStatus,
  listCalibrationSets,
  listCoverageEstimates,
  listDirectionalCoverageAnalyses,
  listHAATCalculations,
  listPhase2ValidationBundles,
  listPlans,
  retryPhase2ValidationBundle,
  runPhase2ValidationBundle,
  verifyPhase2ValidationExport,
} from "./api";
import type {
  CalibrationSet,
  CoverageEstimate,
  DirectionalCoverageAnalysis,
  HAATCalculation,
  ICS205Plan,
  Incident,
  Phase2ExportVerification,
  Phase2ValidationBundle,
  Phase2ValidationStatus,
  PlanRevision,
} from "./types";

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object"
    ? (value as Record<string, unknown>)
    : {};
}

function displayIdentifier(value: string): string {
  return value.length > 16 ? `${value.slice(0, 12)}…` : value;
}

export function Phase2ValidationWorkspace({
  incident,
}: {
  incident?: Incident;
}) {
  const [profileStatus, setProfileStatus] =
    useState<Phase2ValidationStatus | null>(null);
  const [plans, setPlans] = useState<ICS205Plan[]>([]);
  const [haatCalculations, setHaatCalculations] = useState<HAATCalculation[]>(
    [],
  );
  const [coverageEstimates, setCoverageEstimates] = useState<
    CoverageEstimate[]
  >([]);
  const [directionalAnalyses, setDirectionalAnalyses] = useState<
    DirectionalCoverageAnalysis[]
  >([]);
  const [calibrationSets, setCalibrationSets] = useState<CalibrationSet[]>([]);
  const [bundles, setBundles] = useState<Phase2ValidationBundle[]>([]);
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [verification, setVerification] =
    useState<Phase2ExportVerification | null>(null);

  const approvedRevisions = useMemo(
    () =>
      plans
        .filter((plan) => plan.incident === incident?.id)
        .flatMap((plan) => plan.revisions)
        .filter(
          (revision): revision is PlanRevision =>
            revision.status === "approved",
        ),
    [incident?.id, plans],
  );
  const approvedHaat = useMemo(
    () =>
      haatCalculations.filter(
        (item) =>
          item.status === "approved" && item.calculation_state === "complete",
      ),
    [haatCalculations],
  );
  const approvedCoverage = useMemo(
    () =>
      coverageEstimates.filter(
        (item) =>
          item.status === "approved" && item.calculation_state === "complete",
      ),
    [coverageEstimates],
  );
  const approvedDirectional = useMemo(
    () =>
      directionalAnalyses.filter(
        (item) =>
          item.status === "approved" && item.calculation_state === "complete",
      ),
    [directionalAnalyses],
  );
  const approvedCalibration = useMemo(
    () =>
      calibrationSets.filter(
        (item) =>
          item.status === "approved" && item.calculation_state === "complete",
      ),
    [calibrationSets],
  );

  const canEdit = Boolean(incident?.permissions.includes("rf.edit"));
  const canApprove = Boolean(incident?.permissions.includes("rf.approve"));
  const canExport = Boolean(
    canApprove && incident?.permissions.includes("plan.export"),
  );

  const refresh = useCallback(async () => {
    if (!incident) {
      setPlans([]);
      setHaatCalculations([]);
      setCoverageEstimates([]);
      setDirectionalAnalyses([]);
      setCalibrationSets([]);
      setBundles([]);
      return;
    }
    setLoading(true);
    try {
      const [
        nextStatus,
        nextPlans,
        nextHaat,
        nextCoverage,
        nextDirectional,
        nextCalibration,
        nextBundles,
      ] = await Promise.all([
        getPhase2ValidationStatus(),
        listPlans(),
        listHAATCalculations(incident.id),
        listCoverageEstimates(incident.id),
        listDirectionalCoverageAnalyses(incident.id),
        listCalibrationSets(incident.id),
        listPhase2ValidationBundles(incident.id),
      ]);
      setProfileStatus(nextStatus);
      setPlans(nextPlans);
      setHaatCalculations(nextHaat);
      setCoverageEstimates(nextCoverage);
      setDirectionalAnalyses(nextDirectional);
      setCalibrationSets(nextCalibration);
      setBundles(nextBundles);
      setError("");
    } catch (caught) {
      setError(
        errorMessage(caught, "Unable to load Phase 2 validation evidence."),
      );
    } finally {
      setLoading(false);
    }
  }, [incident]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function handleQueue(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!incident) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusyId("queue");
    setMessage("Queueing immutable source evidence…");
    setError("");
    try {
      await createPhase2ValidationBundle({
        incident: incident.id,
        approved_revision: String(data.get("approved_revision")),
        haat_calculation: String(data.get("haat_calculation")),
        coverage_estimate: String(data.get("coverage_estimate")),
        directional_analysis: String(data.get("directional_analysis")),
        calibration_set: String(data.get("calibration_set")),
      });
      form.reset();
      setMessage("Phase 2 validation evidence queued.");
      await refresh();
    } catch (caught) {
      setError(errorMessage(caught, "Unable to queue validation evidence."));
      setMessage("");
    } finally {
      setBusyId("");
    }
  }

  async function performAction(
    bundle: Phase2ValidationBundle,
    label: string,
    action: (id: string) => Promise<unknown>,
  ) {
    setBusyId(bundle.id);
    setMessage(label);
    setError("");
    try {
      await action(bundle.id);
      setMessage(`${label.replace(/…$/, "")} complete.`);
      await refresh();
    } catch (caught) {
      setError(errorMessage(caught, "The validation action failed."));
      setMessage("");
    } finally {
      setBusyId("");
    }
  }

  async function handleVerify(
    event: FormEvent<HTMLFormElement>,
    bundle: Phase2ValidationBundle,
  ) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusyId(bundle.id);
    setVerification(null);
    setError("");
    try {
      const result = await verifyPhase2ValidationExport(
        bundle.id,
        String(data.get("content_sha256")).trim(),
      );
      setVerification(result);
    } catch (caught) {
      setError(errorMessage(caught, "Unable to verify the export digest."));
    } finally {
      setBusyId("");
    }
  }

  return (
    <section
      className="coverage-panel"
      aria-labelledby="phase2-validation-heading"
    >
      <div className="section-heading">
        <div>
          <p className="eyebrow">Phase 2 release-candidate evidence</p>
          <h2 id="phase2-validation-heading">End-to-end validation bundle</h2>
        </div>
        <span className="count">{bundles.length}</span>
      </div>
      <p className="disclaimer">
        This workspace preserves a version-pinned chain from an approved ICS 205
        plan through HAAT, directional estimates, synthetic observations, and
        incident-local calibration. It supports release review only; it does not
        claim field or scientific validation.
      </p>

      {!incident ? (
        <p className="empty">Select an incident to prepare Phase 2 evidence.</p>
      ) : loading && !profileStatus ? (
        <p role="status" aria-live="polite">
          Loading Phase 2 validation sources…
        </p>
      ) : (
        <>
          {profileStatus && (
            <article className="coverage-engine-card">
              <h3>Validation profile</h3>
              <dl className="evidence-list">
                <div>
                  <dt>Profile</dt>
                  <dd>
                    <strong>{profileStatus.validation_profile_version}</strong>
                  </dd>
                </div>
                <div>
                  <dt>Configured gate</dt>
                  <dd>
                    {profileStatus.approved_for_release_candidate_use
                      ? "Qualified review allowlist enabled"
                      : "Fail closed — qualified review still required"}
                  </dd>
                </div>
                <div>
                  <dt>Execution</dt>
                  <dd>{profileStatus.execution_model}</dd>
                </div>
                {profileStatus.resource_safety_limits && (
                  <div>
                    <dt>Bundle guards</dt>
                    <dd>
                      Up to{" "}
                      {
                        profileStatus.resource_safety_limits
                          .maximum_plan_assignments
                      }{" "}
                      plan rows and{" "}
                      {
                        profileStatus.resource_safety_limits
                          .maximum_calibration_observations
                      }{" "}
                      calibration observations
                    </dd>
                  </div>
                )}
              </dl>
              <p>{profileStatus.cancellation_boundary}</p>
              <p className="disclaimer">{profileStatus.disclaimer}</p>
            </article>
          )}

          {canEdit && (
            <form className="coverage-form" onSubmit={handleQueue}>
              <h3>Queue a version-pinned validation run</h3>
              <p>
                Select approved records from one incident. The server rejects
                mismatched HAAT, coverage, directional, calibration, or RF-input
                chains.
              </p>
              <label>
                Approved ICS 205 revision
                <select name="approved_revision" required>
                  <option value="">Select approved revision</option>
                  {approvedRevisions.map((revision) => (
                    <option key={revision.id} value={revision.id}>
                      Revision {revision.number} · {revision.assignments.length}{" "}
                      rows
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Approved HAAT calculation
                <select name="haat_calculation" required>
                  <option value="">Select HAAT calculation</option>
                  {approvedHaat.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.site_name} · {item.haat_m} m ·{" "}
                      {displayIdentifier(item.result_sha256)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Approved band/environment estimate
                <select name="coverage_estimate" required>
                  <option value="">Select coverage estimate</option>
                  {approvedCoverage.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.site_name} · {item.environment} ·{" "}
                      {item.nominal_distance_m ?? "unsupported"} m
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Approved directional estimate
                <select name="directional_analysis" required>
                  <option value="">Select directional estimate</option>
                  {approvedDirectional.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.site_name} · probable two-way{" "}
                      {item.probable_two_way_distance_m ?? "unsupported"} m
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Approved incident-local calibration
                <select name="calibration_set" required>
                  <option value="">Select calibration set</option>
                  {approvedCalibration.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name} v{item.version} ·{" "}
                      {item.observation_ids.length} observations
                    </option>
                  ))}
                </select>
              </label>
              <button type="submit" disabled={busyId === "queue"}>
                Queue immutable validation evidence
              </button>
            </form>
          )}

          {message && (
            <div aria-live="polite" role="status">
              {message}
            </div>
          )}
          {error && (
            <p className="error-banner" role="alert">
              {error}
            </p>
          )}

          <div className="coverage-results">
            <div className="section-heading">
              <h3>Validation history</h3>
              <button
                type="button"
                onClick={() => void refresh()}
                disabled={loading}
              >
                Refresh status
              </button>
            </div>
            {bundles.length === 0 ? (
              <p className="empty">No Phase 2 validation evidence is queued.</p>
            ) : (
              <div className="resource-grid">
                {bundles.map((bundle) => {
                  const comparison = record(
                    bundle.result_snapshot.deterministic_observation_comparison,
                  );
                  const counts = record(comparison.counts);
                  const sensitivity = record(
                    bundle.result_snapshot.sensitivity,
                  );
                  const coverageSensitivity = record(
                    sensitivity.coverage_distance_m,
                  );
                  const directionalSensitivity = record(
                    sensitivity.directional_distance_m,
                  );
                  return (
                    <article key={bundle.id} className="coverage-engine-card">
                      <div className="section-heading">
                        <h4>
                          {bundle.validation_profile_version} ·{" "}
                          {bundle.job_state}
                        </h4>
                        <span className="count">
                          {bundle.progress_percent}%
                        </span>
                      </div>
                      <div
                        role="progressbar"
                        aria-label={`Validation progress for ${bundle.id}`}
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-valuenow={bundle.progress_percent}
                      >
                        <progress value={bundle.progress_percent} max={100}>
                          {bundle.progress_percent}%
                        </progress>
                      </div>
                      <dl className="evidence-list">
                        <div>
                          <dt>Evidence status</dt>
                          <dd>
                            {bundle.status}
                            {bundle.is_stale ? " · stale" : " · current"}
                          </dd>
                        </div>
                        <div>
                          <dt>Application</dt>
                          <dd>{bundle.app_version}</dd>
                        </div>
                        <div>
                          <dt>Input digest</dt>
                          <dd>
                            <code>{bundle.input_sha256}</code>
                          </dd>
                        </div>
                        {bundle.result_sha256 && (
                          <div>
                            <dt>Result digest</dt>
                            <dd>
                              <code>{bundle.result_sha256}</code>
                            </dd>
                          </div>
                        )}
                      </dl>
                      {bundle.failure_message && (
                        <p role="alert">
                          <strong>{bundle.failure_code}:</strong>{" "}
                          {bundle.failure_message}
                        </p>
                      )}
                      {bundle.is_stale && (
                        <div className="error-banner" role="alert">
                          <strong>Stale evidence:</strong>{" "}
                          {bundle.stale_reasons.join(", ")}. Retain this record
                          and queue a new bundle from current approved sources.
                        </div>
                      )}
                      {bundle.job_state === "complete" && (
                        <div>
                          <h5>Deterministic comparison</h5>
                          <p>
                            Within tolerance:{" "}
                            {String(counts.within_tolerance ?? 0)}
                            {" · "}Outside:{" "}
                            {String(counts.outside_tolerance ?? 0)}
                            {" · "}Not comparable:{" "}
                            {String(counts.not_comparable ?? 0)}
                          </p>
                          <h5>Sensitivity summary</h5>
                          <p>
                            Coverage conservative / nominal / optimistic:{" "}
                            {String(coverageSensitivity.conservative ?? "—")} /{" "}
                            {String(coverageSensitivity.nominal ?? "—")} /{" "}
                            {String(coverageSensitivity.optimistic ?? "—")} m
                          </p>
                          <p>
                            Directional talk-out / talk-in / probable two-way:{" "}
                            {String(directionalSensitivity.talk_out ?? "—")} /{" "}
                            {String(directionalSensitivity.talk_in ?? "—")} /{" "}
                            {String(
                              directionalSensitivity.probable_two_way ?? "—",
                            )}{" "}
                            m
                          </p>
                        </div>
                      )}
                      <div className="button-row">
                        {canEdit && bundle.job_state === "queued" && (
                          <>
                            <button
                              type="button"
                              disabled={busyId === bundle.id}
                              onClick={() =>
                                void performAction(
                                  bundle,
                                  "Running staged validation…",
                                  runPhase2ValidationBundle,
                                )
                              }
                            >
                              Run validation
                            </button>
                            <button
                              type="button"
                              disabled={busyId === bundle.id}
                              onClick={() =>
                                void performAction(
                                  bundle,
                                  "Cancelling queued validation…",
                                  cancelPhase2ValidationBundle,
                                )
                              }
                            >
                              Cancel queued run
                            </button>
                          </>
                        )}
                        {canEdit &&
                          ["failed", "cancelled"].includes(
                            bundle.job_state,
                          ) && (
                            <button
                              type="button"
                              disabled={busyId === bundle.id}
                              onClick={() =>
                                void performAction(
                                  bundle,
                                  "Queueing retained retry…",
                                  retryPhase2ValidationBundle,
                                )
                              }
                            >
                              Queue retry
                            </button>
                          )}
                        {canApprove &&
                          bundle.job_state === "complete" &&
                          bundle.status === "draft" && (
                            <button
                              type="button"
                              disabled={
                                busyId === bundle.id ||
                                !bundle.approval_eligible
                              }
                              title={
                                bundle.approval_eligible
                                  ? "Approve this exact evidence bundle"
                                  : "The configured qualified-review gate is closed or evidence is stale"
                              }
                              onClick={() =>
                                void performAction(
                                  bundle,
                                  "Approving exact validation evidence…",
                                  approvePhase2ValidationBundle,
                                )
                              }
                            >
                              Approve evidence
                            </button>
                          )}
                        {canExport &&
                          bundle.status === "approved" &&
                          !bundle.is_stale && (
                            <button
                              type="button"
                              disabled={busyId === bundle.id}
                              onClick={() =>
                                void performAction(
                                  bundle,
                                  "Preparing controlled export…",
                                  downloadPhase2ValidationBundle,
                                )
                              }
                            >
                              Download controlled JSON
                            </button>
                          )}
                      </div>
                      {canExport && bundle.status === "approved" && (
                        <form
                          className="compact-form"
                          onSubmit={(event) => void handleVerify(event, bundle)}
                        >
                          <label>
                            Verify a downloaded SHA-256 digest
                            <input
                              name="content_sha256"
                              pattern="[0-9a-fA-F]{64}"
                              maxLength={64}
                              autoComplete="off"
                              required
                            />
                          </label>
                          <button type="submit" disabled={busyId === bundle.id}>
                            Verify audited export
                          </button>
                        </form>
                      )}
                      {verification && (
                        <p role="status">
                          {verification.verified
                            ? `Verified against audit event ${verification.audit_event_id}.`
                            : verification.detail}
                        </p>
                      )}
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
