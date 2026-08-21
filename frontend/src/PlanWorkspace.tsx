import {
  Fragment,
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  approvePlanRevision,
  collaborationDeviceId,
  comparePlanRevisions,
  copyPlanRevision,
  createPlan,
  createPlanRelationship,
  downloadPlanPdf,
  getPlanPublicationSummary,
  heartbeatCollaborationPresence,
  listCollaborationChanges,
  listCollaborationPresence,
  listPlans,
  listSubscriberProfiles,
  listSubscriberProfileVersions,
  previewPlanApprovalPdf,
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

const PRESENCE_FIELDS: Record<string, string> = {
  function: "function",
  channelName: "channel_name",
  assignment: "assignment",
  operatingClassification: "operating_classification",
  technologySubtype: "technology_subtype",
  rxMHz: "rx_frequency_hz",
  rxAccessCode: "rx_squelch",
  txMHz: "tx_frequency_hz",
  txAccessCode: "tx_squelch",
  mode: "mode",
  structuredNote: "structured_note",
  remarks: "remarks",
  contactName: "contact_name",
  siteAddress: "site_address",
  phoneNumbers: "phone_numbers",
  contact24Hour: "contact_24_hour",
  contact_name: "contact_name",
  site_address: "site_address",
  phone_numbers: "phone_numbers",
  contact_24_hour: "contact_24_hour",
  publicationPurpose: "contact_publication_purpose",
  publicationPlacement: "contact_publication_placement",
  preparedByName: "prepared_by_name",
  preparedByPosition: "prepared_by_position",
};

function displayDate(value?: string) {
  if (!value) return "Not set";
  return new Intl.DateTimeFormat("en-US", {
    month: "2-digit",
    day: "2-digit",
    year: "numeric",
  }).format(new Date(value));
}

function displayTime(value?: string) {
  if (!value) return "Not set";
  return new Intl.DateTimeFormat("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

function displayFrequency(value: number | null) {
  return value === null ? "" : (value / 1_000_000).toFixed(4);
}

function displayMode(value: string) {
  const normalized = value.trim().toUpperCase();
  if (["A", "D", "M"].includes(normalized)) return normalized;
  if (normalized.includes("MIX")) return "M";
  if (normalized.includes("ANALOG") || ["FM", "FMN"].includes(normalized)) {
    return "A";
  }
  if (
    ["DIGITAL", "P25", "DMR", "NXDN"].some((item) => normalized.includes(item))
  ) {
    return "D";
  }
  return "";
}

export function PlanWorkspace({ incident }: { incident?: Incident }) {
  const [plans, setPlans] = useState<ICS205Plan[]>([]);
  const [selectedRevisionId, setSelectedRevisionId] = useState("");
  const [selectedRows, setSelectedRows] = useState<string[]>([]);
  const [comparison, setComparison] = useState<RevisionComparison | null>(null);
  const [presence, setPresence] = useState<CollaborationPresence[]>([]);
  const [changes, setChanges] = useState<CollaborationChange[]>([]);
  const [activeConflict, setActiveConflict] =
    useState<CollaborationChange | null>(null);
  const [selectedConflictFields, setSelectedConflictFields] = useState<
    string[]
  >([]);
  const presenceLocation = useRef<{
    object_id?: string | null;
    field_name?: string;
  }>({});
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
    setSelectedRevisionId("");
  }, [incident?.id]);

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
  const draftRevision = revisions.find((item) => item.status === "draft");
  const revision =
    revisions.find((item) => item.id === selectedRevisionId) ??
    draftRevision ??
    revisions[0];
  const canEdit =
    incident?.permissions.includes("plan.edit") && !revision?.is_locked;
  const canApprove = incident?.permissions.includes("plan.approve");
  const canExport = incident?.permissions.includes("plan.export");
  const revisionId = revision?.id;
  const operationalPeriod = incident?.operational_periods.find(
    (period) => period.id === plan?.operational_period,
  );

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
    setPresence([]);
    setChanges([]);
    setActiveConflict(null);
    setSelectedRows([]);
    presenceLocation.current = {};

    async function synchronize() {
      try {
        await heartbeatCollaborationPresence(
          revisionId,
          canEdit ? "editing" : "viewing",
          section,
          presenceLocation.current,
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

  useEffect(() => {
    setSelectedConflictFields(activeConflict?.affected_fields ?? []);
  }, [activeConflict]);

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

  async function handlePreparedBy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    await runMutation({
      operation: "revision.update",
      baseVersion: revision!.collaboration_version,
      changes: {
        prepared_by_name: String(data.get("preparedByName")),
        prepared_by_position: String(data.get("preparedByPosition")),
      },
    });
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

  async function configureContactPublication(
    event: FormEvent<HTMLFormElement>,
    row: PlanAssignment,
  ) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const publishedFields = [
      "contact_name",
      "site_address",
      "phone_numbers",
      "contact_24_hour",
    ].filter((field) => data.get(field) === "on");
    const outcome = await runMutation({
      operation: "assignment.update",
      objectId: row.id,
      baseVersion: row.collaboration_version,
      changes: {
        published_contact_fields: publishedFields,
        contact_publication_purpose: String(data.get("publicationPurpose")),
        contact_publication_placement: String(data.get("publicationPlacement")),
      },
    });
    if (outcome?.disposition === "saved") {
      setMessage(
        publishedFields.length
          ? "Contact publication selection saved for approval preview."
          : "Contact information will remain restricted and off the ICS 205.",
      );
    }
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

  async function applyConflictValues(
    decision: "reapply" | "replace",
    fields: string[],
  ) {
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
    const changes = Object.fromEntries(
      fields
        .filter((field) =>
          Object.prototype.hasOwnProperty.call(
            activeConflict.proposed_snapshot,
            field,
          ),
        )
        .map((field) => [field, activeConflict.proposed_snapshot[field]]),
    );
    if (Object.keys(changes).length === 0) {
      setMessage("Select at least one proposed field to apply.");
      return;
    }
    if (
      decision === "replace" &&
      !window.confirm(
        "Intentionally replace the currently saved values with your complete retained proposal? This creates a new audited version.",
      )
    ) {
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
        changes,
      });
      if (replacement.disposition !== "saved") {
        setActiveConflict(replacement);
        setMessage(
          "The record changed again. Review the latest saved values before choosing.",
        );
        return;
      }
      await resolveCollaborationConflict(activeConflict.id, {
        decision,
        explanation:
          decision === "replace"
            ? "User intentionally replaced the current values with the retained proposal."
            : `User reapplied selected retained fields: ${Object.keys(changes).join(", ")}.`,
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

  async function handleApproveRevision() {
    if (!revision) return;
    try {
      const summary = await getPlanPublicationSummary(revision.id);
      const contactNotice = summary.has_published_contacts
        ? `\n\nRestricted contact fields selected for publication:\n${summary.contact_publications
            .map(
              (item) =>
                `Row ${item.position} ${item.channel_name}: ${item.fields.join(", ")} → ${
                  item.placement === "special_instructions"
                    ? "Special Instructions"
                    : "row Remarks"
                } — ${item.purpose}`,
            )
            .join("\n")}`
        : "\n\nNo restricted contact information will be published.";
      if (
        !window.confirm(
          `Approve and permanently lock revision ${revision.number}? Later changes require a copied draft.${contactNotice}`,
        )
      ) {
        return;
      }
      await approvePlanRevision(revision.id, {
        confirm_contact_publication: summary.has_published_contacts,
        publication_digest: summary.digest,
      });
      setMessage("");
      await refresh();
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Plan approval failed.",
      );
    }
  }

  async function handleCopyRevision() {
    if (!revision) return;
    try {
      const copied = await copyPlanRevision(revision.id);
      setSelectedRevisionId(copied.id);
      setMessage(
        `Draft revision ${copied.number} was created. Approved revision ${revision.number} remains locked and exportable.`,
      );
      await refresh();
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Draft creation failed.",
      );
    }
  }

  if (!incident)
    return <p className="empty">Select an incident to work on its ICS-205.</p>;

  return (
    <section
      className="plan-panel"
      aria-labelledby="plan-heading"
      onFocusCapture={(event) => {
        const target = event.target as HTMLInputElement | HTMLSelectElement;
        const fieldName = PRESENCE_FIELDS[target.name];
        const row = target.closest<HTMLElement>("[data-presence-object]");
        presenceLocation.current = {
          object_id: row?.dataset.presenceObject ?? null,
          field_name: fieldName ?? "",
        };
      }}
    >
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
            {revisions.length > 1 && (
              <label>
                View revision
                <select
                  value={revision.id}
                  onChange={(event) =>
                    setSelectedRevisionId(event.target.value)
                  }
                >
                  {revisions.map((item) => (
                    <option key={item.id} value={item.id}>
                      R{item.number} · {item.status}
                    </option>
                  ))}
                </select>
              </label>
            )}
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
              incident.permissions.includes("plan.edit") &&
              !draftRevision && (
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => void handleCopyRevision()}
                >
                  Create new draft from approved version
                </button>
              )}
            {revision.is_locked && draftRevision && (
              <button
                type="button"
                className="secondary-button"
                onClick={() => setSelectedRevisionId(draftRevision.id)}
              >
                Open newer draft R{draftRevision.number}
              </button>
            )}
          </div>
          {revision.is_locked && draftRevision && (
            <p className="form-note" role="status">
              Approved revision {revision.number} remains locked and available
              for official export. Draft revision {draftRevision.number} is the
              current editable continuation.
            </p>
          )}
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
                        `${person.display_name} (${person.incident_role})${person.is_current_user ? " (you)" : ""}: ${person.mode}${
                          person.field_name
                            ? ` ${person.object_id ? `row ${person.object_id.slice(0, 8)}, ` : ""}${person.field_name.replaceAll("_", " ")}`
                            : ""
                        }`,
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
              {typeof activeConflict.result.intervening_actor_display_name ===
                "string" && (
                <p>
                  The saved version was changed by{" "}
                  <strong>
                    {String(
                      activeConflict.result.intervening_actor_display_name,
                    )}
                  </strong>
                  .
                </p>
              )}
              <div className="conflict-comparison" role="group">
                {activeConflict.affected_fields.map((field) => (
                  <label key={field}>
                    <input
                      type="checkbox"
                      checked={selectedConflictFields.includes(field)}
                      onChange={(event) =>
                        setSelectedConflictFields((current) =>
                          event.target.checked
                            ? [...current, field]
                            : current.filter((item) => item !== field),
                        )
                      }
                    />
                    <strong>{field.replaceAll("_", " ")}</strong>
                    <span>
                      Proposed:{" "}
                      {JSON.stringify(activeConflict.proposed_snapshot[field])}
                    </span>
                    <span>
                      Saved:{" "}
                      {JSON.stringify(activeConflict.current_snapshot[field])}
                    </span>
                  </label>
                ))}
              </div>
              <div className="button-row">
                <button type="button" onClick={() => void discardConflict()}>
                  Keep currently saved values
                </button>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() =>
                    void applyConflictValues("reapply", selectedConflictFields)
                  }
                >
                  Reapply selected fields
                </button>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() =>
                    void applyConflictValues(
                      "replace",
                      activeConflict.affected_fields,
                    )
                  }
                >
                  Intentionally replace with complete proposal
                </button>
              </div>
            </section>
          )}
          <section
            className="ics205-screen-form"
            aria-labelledby="ics205-form-title"
          >
            <h3 id="ics205-form-title">
              Incident Radio Communications Plan (ICS 205)
            </h3>
            <div className="ics205-form-header">
              <section>
                <strong>1. Incident Name:</strong>
                <span>{incident.name}</span>
              </section>
              <section>
                <strong>2. Date/Time Prepared:</strong>
                <span>
                  {revision.approved_at
                    ? `${displayDate(revision.approved_at)} ${displayTime(revision.approved_at)}`
                    : "Completed when approved"}
                </span>
              </section>
              <section>
                <strong>3. Operational Period:</strong>
                <span>
                  Date From: {displayDate(operationalPeriod?.starts_at)}
                </span>
                <span>Date To: {displayDate(operationalPeriod?.ends_at)}</span>
                <span>
                  Time From: {displayTime(operationalPeriod?.starts_at)}
                </span>
                <span>Time To: {displayTime(operationalPeriod?.ends_at)}</span>
              </section>
            </div>
            {canEdit && (
              <details className="ics205-entry-panel" open>
                <summary>Add a Basic Radio Channel Use row</summary>
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
                    <select
                      name="operatingClassification"
                      required
                      defaultValue=""
                    >
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
                    If exactly one frequency is blank, the Toolkit will ask you
                    to confirm transmit-only or receive-only intent. Named
                    systems and dynamic pools intentionally omit both fixed
                    frequencies.
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
              </details>
            )}
            <div className="ics205-channel-section">
              <strong>4. Basic Radio Channel Use:</strong>
              <div className="ics205-table-scroll">
                <table className="ics205-channel-table">
                  <caption className="sr-only">ICS-205 assignment rows</caption>
                  <thead>
                    <tr>
                      <th scope="col">
                        Zone
                        <br />
                        Grp.
                      </th>
                      <th scope="col">Ch #</th>
                      <th scope="col">Function</th>
                      <th scope="col">
                        Channel Name/Trunked Radio System Talkgroup
                      </th>
                      <th scope="col">Assignment</th>
                      <th scope="col">
                        RX Freq
                        <br />N or W
                      </th>
                      <th scope="col">RX Tone/NAC</th>
                      <th scope="col">
                        TX Freq
                        <br />N or W
                      </th>
                      <th scope="col">TX Tone/NAC</th>
                      <th scope="col">
                        Mode
                        <br />
                        (A, D, or M)
                      </th>
                      <th scope="col">Remarks</th>
                      {canEdit && <th scope="col">Row controls</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {revision.assignments.map((row, index) => (
                      <Fragment key={row.id}>
                        <tr data-presence-object={row.id}>
                          <td aria-label="Zone or group"></td>
                          <td>{index + 1}</td>
                          <td>{row.function}</td>
                          <td>{row.channel_name}</td>
                          <td>{row.assignment}</td>
                          <td>{displayFrequency(row.rx_frequency_hz)}</td>
                          <td>{row.rx_squelch}</td>
                          <td>{displayFrequency(row.tx_frequency_hz)}</td>
                          <td>{row.tx_squelch}</td>
                          <td>{displayMode(row.mode)}</td>
                          <td>
                            {row.structured_note && (
                              <strong>
                                {row.structured_note.replaceAll("_", " ")}{" "}
                                ·{" "}
                              </strong>
                            )}
                            {row.remarks ||
                              (displayMode(row.mode) ? "" : row.mode)}
                          </td>
                          {canEdit && (
                            <td className="ics205-row-controls">
                              <label>
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
                                Select
                              </label>
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
                                disabled={
                                  index === revision.assignments.length - 1
                                }
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
                            </td>
                          )}
                        </tr>
                        {canEdit &&
                          (row.contact_name ||
                            row.site_address ||
                            row.phone_numbers ||
                            row.contact_24_hour) && (
                            <tr className="ics205-contact-row">
                              <td colSpan={12}>
                                <form
                                  className="contact-publication-form"
                                  onSubmit={(event) =>
                                    void configureContactPublication(event, row)
                                  }
                                >
                                  <strong>
                                    ICS 205 contact publication for row{" "}
                                    {index + 1}
                                  </strong>
                                  {[
                                    [
                                      "contact_name",
                                      "Contact name",
                                      row.contact_name,
                                    ],
                                    [
                                      "site_address",
                                      "Site address",
                                      row.site_address,
                                    ],
                                    [
                                      "phone_numbers",
                                      "Phone numbers",
                                      row.phone_numbers,
                                    ],
                                    [
                                      "contact_24_hour",
                                      "24-hour contact",
                                      row.contact_24_hour,
                                    ],
                                  ].map(
                                    ([field, label, value]) =>
                                      value && (
                                        <label key={field}>
                                          <input
                                            type="checkbox"
                                            name={field}
                                            defaultChecked={row.published_contact_fields.includes(
                                              field as
                                                | "contact_name"
                                                | "site_address"
                                                | "phone_numbers"
                                                | "contact_24_hour",
                                            )}
                                          />
                                          {label}
                                        </label>
                                      ),
                                  )}
                                  <label>
                                    Operational purpose
                                    <input
                                      name="publicationPurpose"
                                      defaultValue={
                                        row.contact_publication_purpose
                                      }
                                      placeholder="SOW, gateway, property, fuel, or technical support"
                                    />
                                  </label>
                                  <label>
                                    Official-form placement
                                    <select
                                      name="publicationPlacement"
                                      defaultValue={
                                        row.contact_publication_placement
                                      }
                                    >
                                      <option value="remarks">
                                        This row’s Remarks
                                      </option>
                                      <option value="special_instructions">
                                        Plan-wide Special Instructions
                                      </option>
                                    </select>
                                  </label>
                                  <button type="submit">
                                    Save publication selection
                                  </button>
                                </form>
                              </td>
                            </tr>
                          )}
                      </Fragment>
                    ))}
                    {revision.assignments.length === 0 && (
                      <tr>
                        <td
                          colSpan={canEdit ? 12 : 11}
                          className="ics205-empty-row"
                        >
                          No radio channel rows have been entered.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
            <section className="ics205-special-instructions">
              <strong>5. Special Instructions:</strong>
              <p>
                Planning output only. This form is not frequency coordination
                approval, spectrum authorization, a propagation study, or a
                guarantee of coverage.
              </p>
            </section>
            <div className="ics205-prepared-by">
              <strong>6. Prepared by (Communications Unit Leader)</strong>
              {canEdit ? (
                <form onSubmit={handlePreparedBy}>
                  <label>
                    Name
                    <input
                      name="preparedByName"
                      defaultValue={revision.prepared_by_name}
                      maxLength={160}
                    />
                  </label>
                  <label>
                    Position
                    <input
                      name="preparedByPosition"
                      defaultValue={revision.prepared_by_position}
                      maxLength={160}
                    />
                  </label>
                  <button type="submit">Save preparer</button>
                </form>
              ) : (
                <span>
                  Name: {revision.prepared_by_name || "Not entered"}
                  {revision.prepared_by_position
                    ? ` · ${revision.prepared_by_position}`
                    : ""}
                </span>
              )}
              <span>Signature: Not captured electronically</span>
            </div>
            <div className="ics205-form-footer">
              <strong>ICS 205</strong>
              <span>IAP Page _____</span>
              <span>
                Date/Time:{" "}
                {revision.approved_at
                  ? `${displayDate(revision.approved_at)} ${displayTime(revision.approved_at)}`
                  : "Pending approval"}
              </span>
            </div>
          </section>
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
                  onClick={() => void handleApproveRevision()}
                >
                  Approve and lock revision
                </button>
              )}
            {canApprove && !revision.is_locked && (
              <button
                className="secondary-button"
                type="button"
                onClick={() =>
                  void run(() => previewPlanApprovalPdf(revision.id))
                }
              >
                Preview exact approval PDF
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
            Contact details remain restricted unless an authorized planner
            selects specific fields, records an operational purpose, previews
            the PDF, and confirms publication during approval.
          </p>
        </>
      )}
    </section>
  );
}
