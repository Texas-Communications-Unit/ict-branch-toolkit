import { type FormEvent, useEffect, useMemo, useState } from "react";

import {
  approveDeconflictionAnalysis,
  createDeconflictionAnalysis,
  getDeconflictionStatus,
  listConventionalChannels,
  listDeconflictionAnalyses,
  listPlans,
} from "./api";
import type {
  ConventionalChannel,
  DeconflictionAnalysis,
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
  return value === null ? "Missing" : `${(value / 1_000_000).toFixed(5)} MHz`;
}

function WarningEvidence({ warning }: { warning: DeconflictionWarning }) {
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
              <th scope="col">Receive</th>
              <th scope="col">Transmit</th>
              <th scope="col">Squelch evidence</th>
            </tr>
          </thead>
          <tbody>
            {warning.compared_inputs.map((input) => (
              <tr key={input.id}>
                <th scope="row">{input.name}</th>
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
    </article>
  );
}

export function DeconflictionWorkspace({ incident }: { incident?: Incident }) {
  const [ruleStatus, setRuleStatus] =
    useState<DeconflictionRuleSetStatus | null>(null);
  const [plans, setPlans] = useState<ICS205Plan[]>([]);
  const [channels, setChannels] = useState<ConventionalChannel[]>([]);
  const [analyses, setAnalyses] = useState<DeconflictionAnalysis[]>([]);
  const [selectedResourceIds, setSelectedResourceIds] = useState<Set<string>>(
    new Set(),
  );
  const [resourceSearch, setResourceSearch] = useState("");
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
  const visibleChannels = useMemo(() => {
    const query = resourceSearch.trim().toLocaleLowerCase();
    return channels
      .filter(
        (channel) =>
          channel.is_active && channel.release.effective_status === "effective",
      )
      .filter((channel) =>
        query
          ? [
              channel.identifier,
              channel.name,
              channel.channel_use,
              channel.jurisdiction,
              channel.release.source.name,
            ].some((value) => value.toLocaleLowerCase().includes(query))
          : true,
      );
  }, [channels, resourceSearch]);

  useEffect(() => {
    let active = true;
    if (!incident) {
      setRuleStatus(null);
      setPlans([]);
      setChannels([]);
      setAnalyses([]);
      setSelectedResourceIds(new Set());
      setResourceSearch("");
      setError("");
      return;
    }
    setLoading(true);
    setError("");
    Promise.all([
      getDeconflictionStatus(),
      listPlans(),
      listConventionalChannels(),
      listDeconflictionAnalyses(incident.id),
    ])
      .then(([nextStatus, nextPlans, nextChannels, nextAnalyses]) => {
        if (!active) return;
        setRuleStatus(nextStatus);
        setPlans(nextPlans);
        setChannels(nextChannels);
        setAnalyses(nextAnalyses);
        setSelectedResourceIds(new Set());
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

  function toggleResource(id: string) {
    setSelectedResourceIds((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
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
        active_resources: [...selectedResourceIds],
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
        Evaluate an approved ICS-205 against a versioned provisional rule set.
        Results identify evidence for qualified review; they are not frequency
        coordination, spectrum authorization, or a propagation study.
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
                    : "Provisional rule set—qualified practitioner review required"}
                </span>
              </div>
              <p>
                Inclusive adjacent-channel threshold:{" "}
                {ruleStatus.adjacent_channel_threshold_hz.toLocaleString()} Hz.
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
                rings. Select any additional active library resources that
                should be checked for omission from the ICS-205.
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
              <fieldset>
                <legend>
                  Active resources to check for omission (
                  {selectedResourceIds.size} selected)
                </legend>
                <label>
                  Search active resources
                  <input
                    type="search"
                    value={resourceSearch}
                    onChange={(event) => setResourceSearch(event.target.value)}
                    placeholder="Channel, identifier, use, jurisdiction, or source"
                  />
                </label>
                <div className="resource-checklist">
                  {visibleChannels.length === 0 ? (
                    <p className="empty">No matching active resources.</p>
                  ) : (
                    visibleChannels.map((channel) => (
                      <div className="resource-option" key={channel.id}>
                        <input
                          type="checkbox"
                          aria-label={`Select ${channel.name}`}
                          checked={selectedResourceIds.has(channel.id)}
                          onChange={() => toggleResource(channel.id)}
                        />
                        <span>
                          <strong>{channel.name}</strong>
                          <small>
                            {channel.identifier} ·{" "}
                            {frequency(channel.rx_frequency_hz)} ·{" "}
                            {channel.release.source.name}
                          </small>
                        </span>
                      </div>
                    ))
                  )}
                </div>
              </fieldset>
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
                  <div className="haat-result-heading">
                    <div>
                      <h4>
                        Revision {analysis.revision_number} ·{" "}
                        {analysis.warning_count} warnings
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
                        ruleStatus?.approved_for_operational_use && (
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
                        Approval remains disabled until COML, COMT, COMC, and
                        frequency-coordination practitioners approve this exact
                        rule-set version.
                      </p>
                    )}
                  <details>
                    <summary>Evidence digests and frozen input summary</summary>
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
                        <dd>{analysis.input_snapshot.assignments.length}</dd>
                      </div>
                      <div>
                        <dt>Selected active resources</dt>
                        <dd>
                          {
                            analysis.input_snapshot.selected_active_resources
                              .length
                          }
                        </dd>
                      </div>
                    </dl>
                  </details>
                  <div className="deconfliction-warning-list">
                    {analysis.result_snapshot.warnings.length === 0 ? (
                      <p>
                        No warning matched this exact provisional rule set. This
                        is not a finding of coordination or authorization.
                      </p>
                    ) : (
                      analysis.result_snapshot.warnings.map(
                        (warning, index) => (
                          <WarningEvidence
                            key={`${warning.rule_id}-${warning.compared_inputs
                              .map((input) => input.id)
                              .join("-")}-${index}`}
                            warning={warning}
                          />
                        ),
                      )
                    )}
                  </div>
                  <p className="form-note">
                    {analysis.result_snapshot.disclaimer}
                  </p>
                </article>
              ))
            )}
          </div>
        </>
      )}
    </section>
  );
}
