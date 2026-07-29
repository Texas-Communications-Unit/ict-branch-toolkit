import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  approvePlanRevision,
  collaborationDeviceId,
  comparePlanRevisions,
  copyPlanRevision,
  createPlan,
  createPlanRelationship,
  downloadPlanPdf,
  heartbeatCollaborationPresence,
  listCollaborationChanges,
  listCollaborationPresence,
  listPlans,
  listSubscriberProfiles,
  listSubscriberProfileVersions,
  releaseCollaborationPresence,
  resolveCollaborationConflict,
  sendCollaborationMutation,
} from "./api";
import type {
  AssignmentOperatingClassification,
  AssignmentTechnologySubtype,
  CollaborationChange,
  CollaborationOperation,
  CollaborationPresence,
  ICS205Plan,
  Incident,
  PlanAssignment,
  RevisionComparison,
  SubscriberProfileVersion,
} from "./types";

const OPERATING_CLASSIFICATIONS: {
  value: AssignmentOperatingClassification;
  label: string;
}[] = [
  { value: "fixed_pair", label: "Fixed-frequency pair" },
  { value: "transmit_only", label: "Broadcast/transmit-only" },
  { value: "receive_only", label: "Receive-only" },
  {
    value: "named_system",
    label: "Named system channel — frequencies intentionally omitted",
  },
  { value: "dynamic_pool", label: "Dynamic/multi-channel pool" },
  { value: "not_determined", label: "Not yet determined (draft only)" },
];

const TECHNOLOGY_SUBTYPES: {
  value: Exclude<AssignmentTechnologySubtype, "">;
  label: string;
}[] = [
  { value: "trunked_talkgroup", label: "Trunked talkgroup" },
  { value: "lte_5g", label: "LTE/5G" },
  { value: "scada", label: "SCADA" },
  { value: "spread_spectrum", label: "Spread-spectrum" },
  { value: "other", label: "Other system" },
];

export function PlanWorkspace({ incident }: { incident?: Incident }) {
  const [plans, setPlans] = useState<ICS205Plan[]>([]);
  const [selectedRows, setSelectedRows] = useState<string[]>([]);
  const [comparison, setComparison] = useState<RevisionComparison | null>(null);
  const [presence, setPresence] = useState<CollaborationPresence[]>([]);
  const [changes, setChanges] = useState<CollaborationChange[]>([]);
  const [activeConflict, setActiveConflict] =
    useState<CollaborationChange | null>(null);
  const [collaborationStatus, setCollaborationStatus] = useState("");
  const [subscriberProfileVersions, setSubscriberProfileVersions] = useState<
    { version: SubscriberProfileVersion; label: string }[]
  >([]);
  const [message, setMessage] = useState("");

  const refresh = useCallback(async () => {
    const items = await listPlans();
    setPlans(items.filter((item) => item.incident === incident?.id));
    window.dispatchEvent(new Event("ict-plans-updated"));
  }, [incident?.id]);

  useEffect(() => {
    let active = true;
    if (incident) {
      void listPlans()
        .then((items) => {
          if (active)
            setPlans(items.filter((item) => item.incident === incident.id));
        })
        .catch(() => {
          if (active) setPlans([]);
        });
    }
    return () => {
      active = false;
    };
  }, [incident]);

  useEffect(() => {
    let active = true;
    if (!incident) {
      setSubscriberProfileVersions([]);
      return;
    }
    void listSubscriberProfiles(incident.id)
      .then(async (profiles) => {
        const versions = await Promise.all(
          profiles.map(async (profile) => ({
            profile,
            versions: await listSubscriberProfileVersions(profile.id),
          })),
        );
        if (!active) return;
        setSubscriberProfileVersions(
          versions.flatMap(({ profile, versions: profileVersions }) =>
            profileVersions
              .filter((version) => version.status === "approved")
              .map((version) => ({
                version,
                label: `${profile.name} · version ${version.number}`,
              })),
          ),
        );
      })
      .catch(() => {
        if (active) setSubscriberProfileVersions([]);
      });
    return () => {
      active = false;
    };
  }, [incident]);

  const plan = plans[0];
  const revisions = useMemo(
    () => [...(plan?.revisions ?? [])].sort((a, b) => b.number - a.number),
    [plan],
  );
  const revision =
    revisions.find((item) => item.status === "draft") ?? revisions[0];
  const canEdit =
    incident?.permissions.includes("plan.edit") && !revision?.is_locked;
  const canApprove = incident?.permissions.includes("plan.approve");
  const canExport = incident?.permissions.includes("plan.export");
  const revisionId = revision?.id;

  useEffect(() => {
    if (!revisionId) {
      setPresence([]);
      setChanges([]);
      setActiveConflict(null);
      setCollaborationStatus("");
      return;
    }
    let active = true;
    const section = "ics205";

    async function synchronize() {
      try {
        await heartbeatCollaborationPresence(
          revisionId,
          canEdit ? "editing" : "viewing",
          section,
        );
        const [currentPresence, history] = await Promise.all([
          listCollaborationPresence(revisionId, section),
          listCollaborationChanges(revisionId),
        ]);
        if (!active) return;
        setPresence(currentPresence);
        setChanges(history);
        setActiveConflict(
          (current) =>
            current ??
            history.find(
              (change) =>
                change.disposition === "conflict" && !change.resolution,
            ) ??
            null,
        );
        setCollaborationStatus(
          "Online collaboration active. Presence and saved changes refresh every 20 seconds.",
        );
      } catch (error) {
        if (!active) return;
        setCollaborationStatus(
          error instanceof Error
            ? `Collaboration connection needs attention: ${error.message}`
            : "Collaboration connection needs attention.",
        );
      }
    }

    void synchronize();
    const interval = window.setInterval(() => {
      void synchronize();
      void refresh().catch((error) => {
        if (!active) return;
        setCollaborationStatus(
          error instanceof Error
            ? `Plan refresh failed: ${error.message}`
            : "Plan refresh failed.",
        );
      });
    }, 20_000);
    return () => {
      active = false;
      window.clearInterval(interval);
      void releaseCollaborationPresence(revisionId, section).catch(() => {
        // The short server lease expires if unload prevents an explicit release.
      });
    };
  }, [canEdit, refresh, revisionId]);

  async function run(action: () => Promise<unknown>) {
    try {
      await action();
      setMessage("");
      await refresh();
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Plan action failed.",
      );
    }
  }

  async function runMutation(input: {
    operation: CollaborationOperation;
    baseVersion: number;
    changes: Record<string, unknown>;
    objectId?: string;
  }): Promise<CollaborationChange | null> {
    try {
      const outcome = await sendCollaborationMutation({
        client_mutation_id: crypto.randomUUID(),
        device_id: collaborationDeviceId(),
        revision: revision!.id,
        operation: input.operation,
        object_id: input.objectId ?? null,
        section: "ics205",
        base_version: input.baseVersion,
        changes: input.changes,
      });
      if (outcome.disposition === "conflict") {
        setActiveConflict(outcome);
        setMessage(
          "Your change was not applied because the saved record changed. Choose how to resolve it below.",
        );
        return outcome;
      }
      if (outcome.disposition === "rejected") {
        setMessage(
          String(outcome.result.detail ?? "The server rejected this change."),
        );
        return outcome;
      }
      setMessage("");
      await refresh();
      return outcome;
    } catch (error) {
      setMessage(
        error instanceof Error
          ? `The change could not be saved: ${error.message}`
          : "The change could not be saved.",
      );
      return null;
    }
  }

  async function handleCreatePlan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    await run(() => createPlan(incident!.id, String(data.get("period"))));
  }

  async function handleAssignment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const rxFrequency = data.get("rxMHz")
      ? Math.round(Number(data.get("rxMHz")) * 1_000_000)
      : null;
    const txFrequency = data.get("txMHz")
      ? Math.round(Number(data.get("txMHz")) * 1_000_000)
      : null;
    const operatingClassification = String(
      data.get("operatingClassification"),
    ) as AssignmentOperatingClassification;
    const technologySubtype = String(
      data.get("technologySubtype") ?? "",
    ) as AssignmentTechnologySubtype;

    if (
      operatingClassification === "fixed_pair" &&
      (rxFrequency === null || txFrequency === null)
    ) {
      setMessage(
        "Fixed-frequency pair requires both receive and transmit frequencies.",
      );
      return;
    }
    if (
      operatingClassification === "transmit_only" &&
      (rxFrequency !== null || txFrequency === null)
    ) {
      setMessage(
        "Broadcast/transmit-only requires a transmit frequency and a blank receive frequency.",
      );
      return;
    }
    if (
      operatingClassification === "receive_only" &&
      (rxFrequency === null || txFrequency !== null)
    ) {
      setMessage(
        "Receive-only requires a receive frequency and a blank transmit frequency.",
      );
      return;
    }
    if (
      ["named_system", "dynamic_pool"].includes(operatingClassification) &&
      (rxFrequency !== null || txFrequency !== null)
    ) {
      setMessage(
        "Named-system and dynamic-pool assignments intentionally omit fixed receive and transmit frequencies.",
      );
      return;
    }
    if (operatingClassification === "named_system" && !technologySubtype) {
      setMessage("Select the technology subtype for a named system channel.");
      return;
    }
    if (
      operatingClassification !== "named_system" &&
      technologySubtype !== ""
    ) {
      setMessage("Technology subtype applies only to a named system channel.");
      return;
    }
    if (
      operatingClassification === "transmit_only" &&
      !window.confirm(
        "Receive frequency is blank. Confirm that this assignment is intentionally broadcast/transmit-only.",
      )
    ) {
      return;
    }
    if (
      operatingClassification === "receive_only" &&
      !window.confirm(
        "Transmit frequency is blank. Confirm that this assignment is intentionally receive-only.",
      )
    ) {
      return;
    }

    const outcome = await runMutation({
      operation: "assignment.create",
      baseVersion: revision!.collaboration_version,
      changes: {
        position: revision!.assignments.length + 1,
        function: String(data.get("function")),
        channel_name: String(data.get("channelName")),
        assignment: String(data.get("assignment")),
        operating_classification: operatingClassification,
        technology_subtype: technologySubtype,
        subscriber_profile_version:
          String(data.get("subscriberProfileVersion") ?? "") || null,
        rx_frequency_hz: rxFrequency,
        rx_squelch: String(data.get("rxAccessCode") ?? "").trim(),
        tx_frequency_hz: txFrequency,
        tx_squelch: String(data.get("txAccessCode") ?? "").trim(),
        mode: String(data.get("mode")),
        structured_note: String(data.get("structuredNote")),
        remarks: String(data.get("remarks")),
        contact_name: String(data.get("contactName")),
        site_address: String(data.get("siteAddress")),
        phone_numbers: String(data.get("phoneNumbers")),
        contact_24_hour: String(data.get("contact24Hour")),
      },
    });
    if (outcome?.disposition === "saved") form.reset();
  }

  async function move(row: PlanAssignment, offset: number) {
    const rows = [...revision!.assignments];
    const index = rows.findIndex((item) => item.id === row.id);
    const target = index + offset;
    if (target < 0 || target >= rows.length) return;
    [rows[index], rows[target]] = [rows[target], rows[index]];
    await runMutation({
      operation: "assignment.reorder",
      baseVersion: revision!.collaboration_version,
      changes: { assignment_ids: rows.map((item) => item.id) },
    });
  }

  async function deleteAssignment(row: PlanAssignment) {
    if (
      !window.confirm(
        `Delete ${row.channel_name}? This removes the assignment from the current draft only. Approved revisions and prior analysis snapshots are not changed.`,
      )
    ) {
      return;
    }
    const outcome = await runMutation({
      operation: "assignment.delete",
      objectId: row.id,
      baseVersion: row.collaboration_version,
      changes: {},
    });
    if (outcome?.disposition !== "saved") return;
    setMessage("Assignment deleted.");
  }

  async function discardConflict() {
    if (!activeConflict) return;
    try {
      await resolveCollaborationConflict(activeConflict.id, {
        decision: "discard",
        explanation: "User chose to keep the currently saved values.",
      });
      setActiveConflict(null);
      setMessage("");
      await refresh();
    } catch (error) {
      setMessage(
        error instanceof Error
          ? `The conflict could not be resolved: ${error.message}`
          : "The conflict could not be resolved.",
      );
    }
  }

  async function replaceWithProposedValues() {
    if (!activeConflict) return;
    const currentVersion = Number(
      activeConflict.current_snapshot.collaboration_version,
    );
    if (!Number.isInteger(currentVersion) || currentVersion < 1) {
      setMessage(
        "The saved version cannot be determined. Reload the plan before resolving this conflict.",
      );
      return;
    }
    try {
      const replacement = await sendCollaborationMutation({
        client_mutation_id: crypto.randomUUID(),
        device_id: collaborationDeviceId(),
        revision: activeConflict.revision,
        operation: activeConflict.operation,
        object_id: activeConflict.object_id,
        section: activeConflict.section,
        base_version: currentVersion,
        changes: activeConflict.proposed_snapshot,
      });
      if (replacement.disposition !== "saved") {
        setActiveConflict(replacement);
        setMessage(
          "The record changed again. Review the latest saved values before choosing.",
        );
        return;
      }
      await resolveCollaborationConflict(activeConflict.id, {
        decision: "replace",
        explanation: "User intentionally applied the retained proposed values.",
        replacement_change: replacement.id,
      });
      setActiveConflict(null);
      setMessage("");
      await refresh();
    } catch (error) {
      setMessage(
        error instanceof Error
          ? `The conflict could not be resolved: ${error.message}`
          : "The conflict could not be resolved.",
      );
    }
  }

  if (!incident)
    return <p className="empty">Select an incident to work on its ICS-205.</p>;

  return (
    <section className="plan-panel" aria-labelledby="plan-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Controlled revision workflow</p>
          <h2 id="plan-heading">ICS-205</h2>
        </div>
        {revision && <span className="count">R{revision.number}</span>}
      </div>
      {message && (
        <p role="alert" className="error">
          {message}
        </p>
      )}
      {!plan ? (
        incident.permissions.includes("plan.edit") ? (
          <form className="compact-form" onSubmit={handleCreatePlan}>
            <label>
              Operational period
              <select name="period" required>
                <option value="">Select period</option>
                {incident.operational_periods.map((period) => (
                  <option key={period.id} value={period.id}>
                    {period.name}
                  </option>
                ))}
              </select>
            </label>
            <button type="submit">Create ICS-205 draft</button>
          </form>
        ) : (
          <p className="empty">No plan is available.</p>
        )
      ) : (
        <>
          <div className="revision-bar">
            <strong>Revision {revision.number}</strong>
            <span className={`status ${revision.status}`}>
              {revision.status}
            </span>
            {revision.is_locked && canExport && (
              <button
                type="button"
                onClick={() => void run(() => downloadPlanPdf(revision.id))}
              >
                Download official PDF
              </button>
            )}
            {revision.is_locked &&
              incident.permissions.includes("plan.edit") && (
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => void run(() => copyPlanRevision(revision.id))}
                >
                  Copy to new draft
                </button>
              )}
          </div>
          <div
            className="collaboration-summary"
            role="status"
            aria-live="polite"
          >
            <strong>Shared online workspace</strong>
            <span>{collaborationStatus}</span>
            <span>
              {presence.length === 0
                ? "No active users reported."
                : presence
                    .map(
                      (person) =>
                        `${person.display_name}${person.is_current_user ? " (you)" : ""}: ${person.mode}`,
                    )
                    .join(" · ")}
            </span>
            <small>
              {changes.length} recent saved, rejected, or conflicting change
              record(s) retained.
            </small>
          </div>
          {activeConflict && (
            <section
              className="conflict-panel"
              aria-labelledby="conflict-heading"
            >
              <h3 id="conflict-heading">Resolve concurrent change</h3>
              <p>
                Nothing was overwritten. Compare your retained proposal with the
                values currently saved, then choose what to do.
              </p>
              <div className="conflict-comparison">
                <div>
                  <strong>Your proposed values</strong>
                  <pre>
                    {JSON.stringify(activeConflict.proposed_snapshot, null, 2)}
                  </pre>
                </div>
                <div>
                  <strong>Currently saved values</strong>
                  <pre>
                    {JSON.stringify(activeConflict.current_snapshot, null, 2)}
                  </pre>
                </div>
              </div>
              <div className="button-row">
                <button type="button" onClick={() => void discardConflict()}>
                  Keep currently saved values
                </button>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => void replaceWithProposedValues()}
                >
                  Apply my proposed values
                </button>
              </div>
            </section>
          )}
          {canEdit && (
            <form className="assignment-form" onSubmit={handleAssignment}>
              <label>
                Function
                <input name="function" required />
              </label>
              <label>
                Channel or talkgroup
                <input name="channelName" required />
              </label>
              <label>
                Assignment
                <input name="assignment" />
              </label>
              <label>
                Operating classification
                <select name="operatingClassification" required defaultValue="">
                  <option value="" disabled>
                    Select classification
                  </option>
                  {OPERATING_CLASSIFICATIONS.map((classification) => (
                    <option
                      key={classification.value}
                      value={classification.value}
                    >
                      {classification.label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Named-system subtype
                <select name="technologySubtype" defaultValue="">
                  <option value="">Not applicable</option>
                  {TECHNOLOGY_SUBTYPES.map((subtype) => (
                    <option key={subtype.value} value={subtype.value}>
                      {subtype.label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                RX MHz
                <input name="rxMHz" type="number" step="0.000001" min="0" />
              </label>
              <label>
                RX access code
                <input
                  name="rxAccessCode"
                  maxLength={40}
                  placeholder="CTCSS, DCS, NAC, or equivalent"
                />
              </label>
              <label>
                TX MHz
                <input name="txMHz" type="number" step="0.000001" min="0" />
              </label>
              <label>
                TX access code
                <input
                  name="txAccessCode"
                  maxLength={40}
                  placeholder="CTCSS, DCS, NAC, or equivalent"
                />
              </label>
              <label>
                Approved subscriber programming profile
                <select name="subscriberProfileVersion" defaultValue="">
                  <option value="">No profile selected</option>
                  {subscriberProfileVersions.map(({ version, label }) => (
                    <option key={version.id} value={version.id}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <p className="form-note">
                If exactly one frequency is blank, the Toolkit will ask you to
                confirm transmit-only or receive-only intent. Named systems and
                dynamic pools intentionally omit both fixed frequencies.
              </p>
              <label>
                Mode
                <input name="mode" />
              </label>
              <label>
                Structured note
                <select name="structuredNote">
                  <option value="">None</option>
                  <option value="remote_base">Remote Base</option>
                  <option value="link">Link</option>
                  <option value="patch">Patch</option>
                  <option value="other">Other</option>
                </select>
              </label>
              <label>
                Remarks
                <input name="remarks" />
              </label>
              <details>
                <summary>Optional contact details</summary>
                <label>
                  Contact name
                  <input name="contactName" />
                </label>
                <label>
                  Site address
                  <input name="siteAddress" />
                </label>
                <label>
                  Phone numbers
                  <input name="phoneNumbers" />
                </label>
                <label>
                  24-hour contact
                  <input name="contact24Hour" />
                </label>
              </details>
              <button type="submit">Insert assignment row</button>
            </form>
          )}
          <div className="assignment-list" aria-label="ICS-205 assignment rows">
            {revision.assignments.map((row, index) => (
              <article className="assignment-row" key={row.id}>
                {canEdit && (
                  <input
                    aria-label={`Select ${row.channel_name} for relationship`}
                    type="checkbox"
                    checked={selectedRows.includes(row.id)}
                    onChange={(event) =>
                      setSelectedRows((current) =>
                        event.target.checked
                          ? [...current, row.id]
                          : current.filter((id) => id !== row.id),
                      )
                    }
                  />
                )}
                <span className="row-number">{index + 1}</span>
                <div>
                  <strong>{row.function}</strong>
                  <span>{row.channel_name}</span>
                  <small>
                    {OPERATING_CLASSIFICATIONS.find(
                      (classification) =>
                        classification.value === row.operating_classification,
                    )?.label ?? row.operating_classification}
                    {row.technology_subtype
                      ? ` · ${
                          TECHNOLOGY_SUBTYPES.find(
                            (subtype) =>
                              subtype.value === row.technology_subtype,
                          )?.label ?? row.technology_subtype
                        }`
                      : ""}
                  </small>
                </div>
                <span>{row.assignment}</span>
                <span>
                  RX{" "}
                  {row.rx_frequency_hz
                    ? `${(row.rx_frequency_hz / 1_000_000).toFixed(6)} MHz`
                    : "not used"}
                  {" · "}TX{" "}
                  {row.tx_frequency_hz
                    ? `${(row.tx_frequency_hz / 1_000_000).toFixed(6)} MHz`
                    : "not used"}
                </span>
                {canEdit && (
                  <div className="row-actions">
                    <button
                      type="button"
                      aria-label={`Move ${row.channel_name} up`}
                      disabled={index === 0}
                      onClick={() => void move(row, -1)}
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      aria-label={`Move ${row.channel_name} down`}
                      disabled={index === revision.assignments.length - 1}
                      onClick={() => void move(row, 1)}
                    >
                      ↓
                    </button>
                    <button
                      type="button"
                      onClick={() => void deleteAssignment(row)}
                    >
                      Delete
                    </button>
                  </div>
                )}
              </article>
            ))}
          </div>
          {canEdit && selectedRows.length >= 2 && (
            <button
              type="button"
              onClick={() =>
                void run(() =>
                  createPlanRelationship({
                    revision: revision.id,
                    relationship_type: "patch",
                    label: "Operator-defined patch",
                    assignments: selectedRows,
                  }),
                )
              }
            >
              Create patch from selected rows
            </button>
          )}
          <div className="button-row">
            {canApprove &&
              !revision.is_locked &&
              revision.assignments.length > 0 && (
                <button
                  type="button"
                  onClick={() =>
                    void run(() => approvePlanRevision(revision.id))
                  }
                >
                  Approve and lock revision
                </button>
              )}
            {revisions.length > 1 && (
              <button
                type="button"
                className="secondary-button"
                onClick={() =>
                  void (async () => {
                    try {
                      setComparison(
                        await comparePlanRevisions(
                          revisions[0].id,
                          revisions[1].id,
                        ),
                      );
                    } catch (error) {
                      setMessage(
                        error instanceof Error
                          ? error.message
                          : "Comparison failed.",
                      );
                    }
                  })()
                }
              >
                Compare latest revisions
              </button>
            )}
          </div>
          {comparison && (
            <div className="comparison" role="status">
              <strong>Revision comparison</strong>
              <p>{comparison.changes.length} changed row(s).</p>
              {comparison.changes.map((change) => (
                <p key={change.key}>
                  Row {change.key}:{" "}
                  {change.changed_fields.join(", ") || "added or removed"}
                </p>
              ))}
            </div>
          )}
          <p className="legal">
            Contact details are access-controlled and are not included in the
            current PDF export.
          </p>
        </>
      )}
    </section>
  );
}
