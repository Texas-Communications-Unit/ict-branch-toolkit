import { type FormEvent, useEffect, useMemo, useState } from "react";

import {
  approveDeconflictionAnalysis,
  createDeconflictionAnalysis,
  createDeconflictionFindingDisposition,
  getDeconflictionStatus,
  listDeconflictionAnalyses,
  listPlans,
} from "./api";
import type {
  DeconflictionAnalysis,
  DeconflictionAnalysisStatus,
  DeconflictionFindingDisposition,
  DeconflictionFindingDispositionValue,
  DeconflictionRuleSetStatus,
  DeconflictionWarning,
  ICS205Plan,
  Incident,
  PlanRevision,
} from "./types";

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

function frequency(value: number | null): string {
  return value === null
    ? "Not used or not recorded"
    : `${(value / 1_000_000).toFixed(5)} MHz`;
}

function WarningEvidence({
  warning,
  dispositions,
  canRecordDisposition,
  busy,
  onRecordDisposition,
}: {
  warning: DeconflictionWarning;
  dispositions: DeconflictionFindingDisposition[];
  canRecordDisposition: boolean;
  busy: boolean;
  onRecordDisposition: (
    disposition: DeconflictionFindingDispositionValue,
    explanation: string,
  ) => Promise<void>;
}) {
  async function handleDisposition(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    await onRecordDisposition(
      String(data.get("disposition")) as DeconflictionFindingDispositionValue,
      String(data.get("explanation")).trim(),
    );
    form.reset();
  }

  return (
    <article className={`deconfliction-warning severity-${warning.severity}`}>
      <div className="warning-heading">
        <div>
          <span className="severity-badge">{warning.severity}</span>
          <h4>
            {warning.rule_id}: {warning.rule_name}
          </h4>
        </div>
        <span>{warning.rule_set_version}</span>
      </div>
      <p>{warning.explanation}</p>
      <div
        className="table-scroll"
        role="region"
        aria-label={`${warning.rule_id} compared inputs`}
      >
        <table>
          <caption>Inputs compared by this warning</caption>
          <thead>
            <tr>
              <th scope="col">Input</th>
              <th scope="col">Function and assignment</th>
              <th scope="col">Classification</th>
              <th scope="col">Receive</th>
              <th scope="col">Transmit</th>
              <th scope="col">Squelch evidence</th>
            </tr>
          </thead>
          <tbody>
            {warning.compared_inputs.map((input) => (
              <tr key={input.id}>
                <th scope="row">{input.name}</th>
                <td>
                  {input.function || "Not recorded"}
                  {input.assignment ? ` · ${input.assignment}` : ""}
                </td>
                <td>
                  {input.operating_classification ??
                    "Legacy classification not recorded"}
                  {input.technology_subtype
                    ? ` · ${input.technology_subtype}`
                    : ""}
                </td>
                <td>{frequency(input.rx_frequency_hz)}</td>
                <td>{frequency(input.tx_frequency_hz)}</td>
                <td>
                  RX {input.rx_squelch || "not recorded"}; TX{" "}
                  {input.tx_squelch || "not recorded"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <details>
        <summary>Evidence and assumptions</summary>
        <dl className="evidence-list">
          <div>
            <dt>Evidence</dt>
            <dd>
              <pre>{JSON.stringify(warning.evidence, null, 2)}</pre>
            </dd>
          </div>
          <div>
            <dt>Assumptions</dt>
            <dd>
              <ul>
                {warning.assumptions.map((assumption) => (
                  <li key={assumption}>{assumption}</li>
                ))}
              </ul>
            </dd>
          </div>
        </dl>
      </details>
      <div className="finding-dispositions">
        <h5>Practitioner disposition history</h5>
        {dispositions.length === 0 ? (
          <p>No disposition has been recorded for this retained finding.</p>
        ) : (
          <ol>
            {dispositions.map((disposition) => (
              <li key={disposition.id}>
                <strong>{disposition.disposition.replaceAll("_", " ")}</strong>{" "}
                — {disposition.explanation} (
                {new Date(disposition.created_at).toLocaleString()}, recorded by
                user {disposition.created_by})
              </li>
            ))}
          </ol>
        )}
        {canRecordDisposition && warning.finding_key ? (
          <form
            className="finding-disposition-form"
            onSubmit={handleDisposition}
          >
            <label>
              Disposition
              <select name="disposition" required defaultValue="">
                <option value="" disabled>
                  Select disposition
                </option>
                <option value="reviewed_no_change">
                  Reviewed — no plan change
                </option>
                <option value="plan_change_required">
                  Plan change required
                </option>
                <option value="special_accommodation_required">
                  Special accommodation required
                </option>
                <option value="source_review_required">
                  Source review required
                </option>
              </select>
            </label>
            <label>
              Explanation
              <textarea name="explanation" maxLength={1000} rows={2} required />
            </label>
            <button type="submit" disabled={busy}>
              Record append-only disposition
            </button>
          </form>
        ) : !warning.finding_key ? (
          <p>
            This retained legacy finding predates deterministic finding keys.
            Its original evidence remains readable, but dispositions must be
            recorded through the process used for that ruleset version.
          </p>
        ) : null}
      </div>
    </article>
  );
}

function AnalysisStatusEvidence({
  status,
}: {
  status: DeconflictionAnalysisStatus;
}) {
  return (
    <article className="deconfliction-status">
      <div className="warning-heading">
        <div>
          <span className="severity-badge">{status.outcome}</span>
          <h4>
            {status.status_id}: {status.status_name}
          </h4>
        </div>
        <span>{status.rule_set_version}</span>
      </div>
      <p>{status.explanation}</p>
      <dl className="evidence-list">
        <div>
          <dt>Assignment</dt>
          <dd>
            {status.assignment.position
              ? `${status.assignment.position}. `
              : ""}
            {status.assignment.name}
          </dd>
        </div>
        <div>
          <dt>Affected rules</dt>
          <dd>{status.affected_rule_ids.join(", ")}</dd>
        </div>
      </dl>
      <details>
        <summary>Retained status evidence</summary>
        <pre>{JSON.stringify(status.evidence, null, 2)}</pre>
      </details>
    </article>
  );
}

export function DeconflictionWorkspace({ incident }: { incident?: Incident }) {
  const [ruleStatus, setRuleStatus] =
    useState<DeconflictionRuleSetStatus | null>(null);
  const [plans, setPlans] = useState<ICS205Plan[]>([]);
  const [analyses, setAnalyses] = useState<DeconflictionAnalysis[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const canEdit = incident?.permissions.includes("rf.edit") ?? false;
  const canApprove = incident?.permissions.includes("rf.approve") ?? false;
  const approvedRevisions = useMemo(
    () =>
      plans
        .filter((plan) => plan.incident === incident?.id)
        .flatMap((plan) =>
          plan.revisions
            .filter((revision) => revision.status === "approved")
            .map((revision) => ({ plan, revision })),
        ),
    [incident?.id, plans],
  );
  useEffect(() => {
    let active = true;
    if (!incident) {
      setRuleStatus(null);
      setPlans([]);
      setAnalyses([]);
      setError("");
      return;
    }
    setLoading(true);
    setError("");
    Promise.all([
      getDeconflictionStatus(),
      listPlans(),
      listDeconflictionAnalyses(incident.id),
    ])
      .then(([nextStatus, nextPlans, nextAnalyses]) => {
        if (!active) return;
        setRuleStatus(nextStatus);
        setPlans(nextPlans);
        setAnalyses(nextAnalyses);
      })
      .catch((loadError: unknown) => {
        if (active) {
          setError(
            errorMessage(loadError, "Unable to load deconfliction evidence."),
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
    setAnalyses(await listDeconflictionAnalyses(incident.id));
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!incident || !canEdit) return;
    const data = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      await createDeconflictionAnalysis({
        incident: incident.id,
        approved_revision: String(data.get("approved_revision")),
      });
      await refreshAnalyses();
    } catch (submitError) {
      setError(
        errorMessage(
          submitError,
          "Unable to create the deconfliction analysis.",
        ),
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleApprove(analysis: DeconflictionAnalysis) {
    if (!canApprove || !ruleStatus?.approved_for_operational_use) return;
    if (
      !window.confirm(
        "Approve and lock this decision-support result with its exact rule set, inputs, warnings, and digests?",
      )
    ) {
      return;
    }
    setBusy(true);
    setError("");
    try {
      await approveDeconflictionAnalysis(analysis.id);
      await refreshAnalyses();
    } catch (approvalError) {
      setError(
        errorMessage(
          approvalError,
          "Unable to approve the deconfliction analysis.",
        ),
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleDisposition(
    analysis: DeconflictionAnalysis,
    warning: DeconflictionWarning,
    disposition: DeconflictionFindingDispositionValue,
    explanation: string,
  ) {
    if (!canEdit || !explanation || !warning.finding_key) return;
    setBusy(true);
    setError("");
    try {
      await createDeconflictionFindingDisposition(analysis.id, {
        finding_key: warning.finding_key,
        disposition,
        explanation,
      });
      await refreshAnalyses();
    } catch (dispositionError) {
      setError(
        errorMessage(
          dispositionError,
          "Unable to record the practitioner disposition.",
        ),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      className="coverage-panel deconfliction-panel"
      aria-labelledby="deconfliction-heading"
    >
      <div className="section-heading">
        <div>
          <p className="eyebrow">Explainable RF decision support</p>
          <h2 id="deconfliction-heading">Frequency deconfliction review</h2>
        </div>
        <span className="count">{analyses.length}</span>
      </div>
      <p className="panel-intro">
        Evaluate an approved ICS-205 against the versioned practitioner-reviewed
        rule contract. Results identify evidence and unevaluated scope for
        qualified review; they do not authorize or prohibit operations.
      </p>

      {!incident ? (
        <p className="empty">
          Select an incident to review RF deconfliction evidence.
        </p>
      ) : loading ? (
        <p role="status" aria-live="polite">
          Loading deconfliction evidence…
        </p>
      ) : (
        <>
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}

          {ruleStatus && (
            <article className="coverage-engine-card">
              <div>
                <strong>{ruleStatus.rule_set_version}</strong>
                <span>
                  {ruleStatus.approved_for_operational_use
                    ? "Qualified practitioner gate recorded"
                    : "Reviewed ruleset—integrated validation and allowlisting required"}
                </span>
              </div>
              <p>
                Inclusive close-frequency screening threshold:{" "}
                {ruleStatus.close_frequency_threshold_hz.toLocaleString()} Hz.
              </p>
              <p>{ruleStatus.squelch_rule}</p>
              <p>{ruleStatus.disclaimer}</p>
              <details>
                <summary>Rules in this exact version</summary>
                <ul>
                  {ruleStatus.rules.map((rule) => (
                    <li key={rule.id}>
                      <strong>
                        {rule.id}: {rule.name}
                      </strong>{" "}
                      ({rule.severity}) — {rule.summary}
                    </li>
                  ))}
                </ul>
              </details>
            </article>
          )}

          {canEdit && (
            <form className="coverage-form" onSubmit={handleCreate}>
              <h3>Run a frozen-plan review</h3>
              <p className="form-note">
                The engine reads only the approved revision and its frozen site
                rings, operating classifications, selected versioned channel
                definitions, and approved subscriber programming profiles.
              </p>
              <label>
                Approved ICS-205 revision
                <select
                  name="approved_revision"
                  required
                  disabled={approvedRevisions.length === 0}
                >
                  <option value="">Select approved revision</option>
                  {approvedRevisions.map(
                    ({
                      plan,
                      revision,
                    }: {
                      plan: ICS205Plan;
                      revision: PlanRevision;
                    }) => (
                      <option key={revision.id} value={revision.id}>
                        {plan.title} · revision {revision.number}
                      </option>
                    ),
                  )}
                </select>
              </label>
              <button
                type="submit"
                disabled={busy || approvedRevisions.length === 0}
              >
                Run deconfliction review
              </button>
            </form>
          )}

          <div className="coverage-results">
            <h3>Immutable analysis history</h3>
            {analyses.length === 0 ? (
              <p className="empty">No deconfliction analyses exist.</p>
            ) : (
              analyses.map((analysis) => (
                <article className="haat-result-card" key={analysis.id}>
                  {(() => {
                    const analysisStatuses =
                      analysis.result_snapshot.analysis_statuses ?? [];
                    return (
                      <>
                        <div className="haat-result-heading">
                          <div>
                            <h4>
                              Revision {analysis.revision_number} ·{" "}
                              {analysis.warning_count} warnings ·{" "}
                              {analysis.result_snapshot.analysis_status_count ??
                                analysisStatuses.length}{" "}
                              scope statuses
                            </h4>
                            <p>
                              {analysis.rule_set_version} · {analysis.status} ·{" "}
                              {new Date(analysis.created_at).toLocaleString()}
                            </p>
                          </div>
                          <div className="state-badges">
                            <span className="state-badge">
                              {analysis.status === "approved"
                                ? "Approved evidence"
                                : "Draft evidence"}
                            </span>
                            {analysis.status === "draft" &&
                              canApprove &&
                              ruleStatus?.approved_for_operational_use &&
                              analysis.rule_set_version ===
                                ruleStatus.rule_set_version && (
                                <button
                                  type="button"
                                  disabled={busy}
                                  onClick={() => void handleApprove(analysis)}
                                >
                                  Approve and lock analysis
                                </button>
                              )}
                          </div>
                        </div>
                        {!ruleStatus?.approved_for_operational_use &&
                          analysis.status === "draft" && (
                            <p className="warning-text">
                              Approval remains disabled until integrated
                              validation is recorded and an administrator
                              allowlists this exact rule-set version.
                            </p>
                          )}
                        <details>
                          <summary>
                            Evidence digests and frozen input summary
                          </summary>
                          <dl className="digest-list">
                            <div>
                              <dt>Input SHA-256</dt>
                              <dd>{analysis.input_sha256}</dd>
                            </div>
                            <div>
                              <dt>Result SHA-256</dt>
                              <dd>{analysis.result_sha256}</dd>
                            </div>
                            <div>
                              <dt>Frozen assignments</dt>
                              <dd>
                                {analysis.input_snapshot.assignments.length}
                              </dd>
                            </div>
                          </dl>
                        </details>
                        <div className="deconfliction-warning-list">
                          {analysis.result_snapshot.warnings.length === 0 ? (
                            <p>
                              No warning matched this exact ruleset. Review the
                              scope statuses below; this is not a finding of
                              coordination, authorization, or universal
                              conflict-free operation.
                            </p>
                          ) : (
                            analysis.result_snapshot.warnings.map(
                              (warning, index) => (
                                <WarningEvidence
                                  key={`${warning.rule_id}-${warning.compared_inputs
                                    .map((input) => input.id)
                                    .join("-")}-${index}`}
                                  warning={warning}
                                  dispositions={analysis.finding_dispositions.filter(
                                    (disposition) =>
                                      warning.finding_key &&
                                      disposition.finding_key ===
                                        warning.finding_key,
                                  )}
                                  canRecordDisposition={
                                    canEdit &&
                                    Boolean(warning.finding_key) &&
                                    analysis.rule_set_version ===
                                      ruleStatus?.rule_set_version
                                  }
                                  busy={busy}
                                  onRecordDisposition={(
                                    disposition,
                                    explanation,
                                  ) =>
                                    handleDisposition(
                                      analysis,
                                      warning,
                                      disposition,
                                      explanation,
                                    )
                                  }
                                />
                              ),
                            )
                          )}
                        </div>
                        <div className="deconfliction-status-list">
                          <h4>Not applicable and not evaluated scope</h4>
                          {analysisStatuses.length === 0 ? (
                            <p>
                              {analysis.result_snapshot.schema_version ===
                              "rf-deconfliction-result-v1"
                                ? "This retained legacy result predates explicit not-applicable and not-evaluated statuses."
                                : "All applicable rule inputs were available for this exact evaluation scope."}
                            </p>
                          ) : (
                            analysisStatuses.map((status, index) => (
                              <AnalysisStatusEvidence
                                key={`${status.status_id}-${status.assignment.id}-${index}`}
                                status={status}
                              />
                            ))
                          )}
                        </div>
                        <p className="form-note">
                          {analysis.result_snapshot.disclaimer}
                        </p>
                      </>
                    );
                  })()}
                </article>
              ))
            )}
          </div>
        </>
      )}
    </section>
  );
}
