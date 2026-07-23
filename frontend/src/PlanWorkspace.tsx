import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  approvePlanRevision,
  comparePlanRevisions,
  copyPlanRevision,
  createPlan,
  createPlanAssignment,
  createPlanRelationship,
  deletePlanAssignment,
  downloadPlanPdf,
  listPlans,
  reorderPlanAssignments,
} from "./api";
import type {
  ICS205Plan,
  Incident,
  PlanAssignment,
  RevisionComparison,
} from "./types";

export function PlanWorkspace({ incident }: { incident?: Incident }) {
  const [plans, setPlans] = useState<ICS205Plan[]>([]);
  const [selectedRows, setSelectedRows] = useState<string[]>([]);
  const [comparison, setComparison] = useState<RevisionComparison | null>(null);
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

  async function handleCreatePlan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    await run(() => createPlan(incident!.id, String(data.get("period"))));
  }

  async function handleAssignment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    await run(() =>
      createPlanAssignment({
        revision: revision!.id,
        position: revision!.assignments.length + 1,
        function: String(data.get("function")),
        channel_name: String(data.get("channelName")),
        assignment: String(data.get("assignment")),
        rx_frequency_hz: data.get("rxMHz")
          ? Math.round(Number(data.get("rxMHz")) * 1_000_000)
          : null,
        tx_frequency_hz: data.get("txMHz")
          ? Math.round(Number(data.get("txMHz")) * 1_000_000)
          : null,
        mode: String(data.get("mode")),
        structured_note: String(data.get("structuredNote")),
        remarks: String(data.get("remarks")),
        contact_name: String(data.get("contactName")),
        site_address: String(data.get("siteAddress")),
        phone_numbers: String(data.get("phoneNumbers")),
        contact_24_hour: String(data.get("contact24Hour")),
      }),
    );
    form.reset();
  }

  async function move(row: PlanAssignment, offset: number) {
    const rows = [...revision!.assignments];
    const index = rows.findIndex((item) => item.id === row.id);
    const target = index + offset;
    if (target < 0 || target >= rows.length) return;
    [rows[index], rows[target]] = [rows[target], rows[index]];
    await run(() =>
      reorderPlanAssignments(
        revision!.id,
        rows.map((item) => item.id),
      ),
    );
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
                RX MHz
                <input name="rxMHz" type="number" step="0.000001" min="0" />
              </label>
              <label>
                TX MHz
                <input name="txMHz" type="number" step="0.000001" min="0" />
              </label>
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
                </div>
                <span>{row.assignment}</span>
                <span>
                  {row.rx_frequency_hz
                    ? `${(row.rx_frequency_hz / 1_000_000).toFixed(6)} MHz`
                    : "No RX"}
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
                      onClick={() =>
                        void run(() => deletePlanAssignment(row.id))
                      }
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
