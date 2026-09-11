import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { listIncidents } from "./api";
import {
  createICS205BAssignment,
  createICS205BForm,
  deleteICS205BAssignment,
  downloadICS205B,
  ICS205BAssignment,
  ICS205BForm,
  listICS205BForms,
  updateICS205BAssignment,
  updateICS205BForm,
} from "./ics205bApi";
import type { Incident } from "./types";

const EMPTY_ASSIGNMENT = {
  assignment: "",
  it_resource_type: "",
  resource_name: "",
  usage_description: "",
  platform: "",
  developer: "",
  login_install: "",
  equipment_location: "",
  poc_information: "",
  remarks: "",
};

type AssignmentDraft = typeof EMPTY_ASSIGNMENT;

function localDateTimeInput(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

function assignmentDraft(item?: ICS205BAssignment): AssignmentDraft {
  if (!item) return { ...EMPTY_ASSIGNMENT };
  return {
    assignment: item.assignment,
    it_resource_type: item.it_resource_type,
    resource_name: item.resource_name,
    usage_description: item.usage_description,
    platform: item.platform,
    developer: item.developer,
    login_install: item.login_install,
    equipment_location: item.equipment_location,
    poc_information: item.poc_information,
    remarks: item.remarks,
  };
}

export function ICS205BWorkspace() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [incidentId, setIncidentId] = useState("");
  const [periodId, setPeriodId] = useState("");
  const [form, setForm] = useState<ICS205BForm | null>(null);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [editingAssignmentId, setEditingAssignmentId] = useState<string | null>(null);
  const [draft, setDraft] = useState<AssignmentDraft>({ ...EMPTY_ASSIGNMENT });

  const incident = useMemo(
    () => incidents.find((item) => item.id === incidentId),
    [incidentId, incidents],
  );
  const period = incident?.operational_periods.find((item) => item.id === periodId);
  const canEdit = incident?.permissions.includes("plan.edit") ?? false;
  const canExport = incident?.permissions.includes("plan.export") ?? false;

  const refreshForm = useCallback(async () => {
    if (!incidentId || !periodId) {
      setForm(null);
      return;
    }
    setLoading(true);
    try {
      const forms = await listICS205BForms(incidentId, periodId);
      setForm(forms[0] ?? null);
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to load ICS 205B.");
    } finally {
      setLoading(false);
    }
  }, [incidentId, periodId]);

  useEffect(() => {
    let active = true;
    void listIncidents()
      .then((items) => {
        if (!active) return;
        setIncidents(items);
        setIncidentId((current) => current || items[0]?.id || "");
      })
      .catch((error) => {
        if (active)
          setMessage(error instanceof Error ? error.message : "Unable to load incidents.");
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const selectedIncident = incidents.find((item) => item.id === incidentId);
    setPeriodId((current) =>
      selectedIncident?.operational_periods.some((item) => item.id === current)
        ? current
        : selectedIncident?.operational_periods[0]?.id || "",
    );
  }, [incidentId, incidents]);

  useEffect(() => {
    void refreshForm();
    setEditingAssignmentId(null);
    setDraft({ ...EMPTY_ASSIGNMENT });
  }, [refreshForm]);

  async function run(action: () => Promise<unknown>, success: string) {
    setLoading(true);
    try {
      await action();
      await refreshForm();
      setMessage(success);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "ICS 205B action failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateForm() {
    if (!incidentId || !periodId) return;
    await run(
      () =>
        createICS205BForm({
          incident: incidentId,
          operational_period: periodId,
          prepared_at: new Date().toISOString(),
        }),
      "ICS 205B created for this operational period.",
    );
  }

  async function handleHeaderSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form) return;
    const data = new FormData(event.currentTarget);
    const preparedAt = String(data.get("prepared_at") || "");
    await run(
      () =>
        updateICS205BForm(form.id, {
          prepared_at: preparedAt ? new Date(preparedAt).toISOString() : null,
          prepared_by_name: String(data.get("prepared_by_name") || ""),
          prepared_by_position: String(data.get("prepared_by_position") || ""),
          prepared_by_phone: String(data.get("prepared_by_phone") || ""),
          prepared_by_signature: String(data.get("prepared_by_signature") || ""),
          incident_location: String(data.get("incident_location") || ""),
          state: String(data.get("state") || ""),
          county: String(data.get("county") || ""),
          city: String(data.get("city") || ""),
        }),
      "ICS 205B header and footer information saved.",
    );
  }

  async function handleAssignmentSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form) return;
    const payload = { form: form.id, ...draft };
    await run(
      () =>
        editingAssignmentId
          ? updateICS205BAssignment(editingAssignmentId, draft)
          : createICS205BAssignment(payload),
      editingAssignmentId ? "Assignment updated." : "Assignment added.",
    );
    setEditingAssignmentId(null);
    setDraft({ ...EMPTY_ASSIGNMENT });
  }

  function beginEdit(item: ICS205BAssignment) {
    setEditingAssignmentId(item.id);
    setDraft(assignmentDraft(item));
    requestAnimationFrame(() =>
      document.getElementById("ics205b-assignment-editor")?.focus(),
    );
  }

  async function removeAssignment(item: ICS205BAssignment) {
    if (!window.confirm(`Delete assignment ${item.position}?`)) return;
    await run(() => deleteICS205BAssignment(item.id), "Assignment deleted.");
    if (editingAssignmentId === item.id) {
      setEditingAssignmentId(null);
      setDraft({ ...EMPTY_ASSIGNMENT });
    }
  }

  async function exportForm(format: "pdf" | "xlsx") {
    if (!form) return;
    setLoading(true);
    try {
      await downloadICS205B(form.id, format);
      setMessage(`ICS 205B ${format.toUpperCase()} export created.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Export failed.");
    } finally {
      setLoading(false);
    }
  }

  const setField = (field: keyof AssignmentDraft, value: string) =>
    setDraft((current) => ({ ...current, [field]: value }));

  return (
    <section className="planning-panel" aria-labelledby="ics205b-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">ITSL planning form</p>
          <h2 id="ics205b-heading">ICS 205B</h2>
        </div>
        <span className="count">{form?.assignments.length ?? 0}</span>
      </div>
      <p>
        Incident Information Management Plan for Information Technology infrastructure and
        services assignments. Excel and PDF exports follow the supplied ICS 205B spreadsheet
        layout and form revision 6/15/2018.
      </p>
      <p className="warning-text">
        <strong>Credential safety:</strong> Login/Install is for instructions or identifiers only.
        Do not enter passwords, API keys, access tokens, private keys, or other credentials.
      </p>

      <div className="form-grid">
        <label>
          Incident
          <select value={incidentId} onChange={(event) => setIncidentId(event.target.value)}>
            <option value="">Select incident</option>
            {incidents.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Operational period
          <select value={periodId} onChange={(event) => setPeriodId(event.target.value)}>
            <option value="">Select operational period</option>
            {incident?.operational_periods.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      {!periodId && incident && (
        <p role="status">Create an operational period before creating an ICS 205B.</p>
      )}
      {periodId && !form && canEdit && (
        <button type="button" onClick={() => void handleCreateForm()} disabled={loading}>
          Create ICS 205B
        </button>
      )}
      {periodId && !form && !canEdit && (
        <p role="status">No ICS 205B exists for this operational period.</p>
      )}

      {form && (
        <>
          <section aria-labelledby="ics205b-form-information">
            <h3 id="ics205b-form-information">Form information</h3>
            <dl className="provenance-grid">
              <div>
                <dt>1. Incident Name</dt>
                <dd>{form.incident_name}</dd>
              </div>
              <div>
                <dt>3. Operational Period</dt>
                <dd>
                  {period?.name ?? form.operational_period_name}: {form.operational_period_starts_at}
                  {" — "}
                  {form.operational_period_ends_at}
                </dd>
              </div>
            </dl>
            <form key={form.updated_at} className="form-grid" onSubmit={handleHeaderSave}>
              <label>
                2. Date/Time Prepared
                <input
                  name="prepared_at"
                  type="datetime-local"
                  defaultValue={localDateTimeInput(form.prepared_at)}
                  disabled={!canEdit}
                />
              </label>
              <label>
                5. Prepared By — Name
                <input name="prepared_by_name" defaultValue={form.prepared_by_name} disabled={!canEdit} />
              </label>
              <label>
                Position
                <input name="prepared_by_position" defaultValue={form.prepared_by_position} disabled={!canEdit} />
              </label>
              <label>
                Phone Number
                <input name="prepared_by_phone" defaultValue={form.prepared_by_phone} disabled={!canEdit} />
              </label>
              <label>
                Signature / typed signature
                <input name="prepared_by_signature" defaultValue={form.prepared_by_signature} disabled={!canEdit} />
              </label>
              <label>
                6. Incident Location
                <input name="incident_location" defaultValue={form.incident_location} disabled={!canEdit} />
              </label>
              <label>
                State
                <input name="state" defaultValue={form.state} disabled={!canEdit} />
              </label>
              <label>
                County
                <input name="county" defaultValue={form.county} disabled={!canEdit} />
              </label>
              <label>
                City
                <input name="city" defaultValue={form.city} disabled={!canEdit} />
              </label>
              {canEdit && <button type="submit">Save form information</button>}
            </form>
          </section>

          <section aria-labelledby="ics205b-assignments-heading">
            <h3 id="ics205b-assignments-heading">
              4. Information Technology Infrastructure &amp; Services Assignment
            </h3>
            <div className="table-wrap" tabIndex={0} aria-label="ICS 205B assignments table">
              <table className="data-table">
                <caption>ICS 205B information technology assignments</caption>
                <thead>
                  <tr>
                    <th scope="col">Assignment</th>
                    <th scope="col">IT Resource Type</th>
                    <th scope="col">Name of Application or Resource</th>
                    <th scope="col">Usage or Description</th>
                    <th scope="col">Platform</th>
                    <th scope="col">Developer</th>
                    <th scope="col">Login/Install</th>
                    <th scope="col">Equipment Location / Web Address, IP Address or SSID</th>
                    <th scope="col">POC Information</th>
                    <th scope="col">Remarks</th>
                    {canEdit && <th scope="col">Actions</th>}
                  </tr>
                </thead>
                <tbody>
                  {form.assignments.length === 0 ? (
                    <tr>
                      <td colSpan={canEdit ? 11 : 10}>No IT assignments have been entered.</td>
                    </tr>
                  ) : (
                    form.assignments.map((item) => (
                      <tr key={item.id}>
                        <td>{item.assignment}</td>
                        <td>{item.it_resource_type}</td>
                        <td>{item.resource_name}</td>
                        <td>{item.usage_description}</td>
                        <td>{item.platform}</td>
                        <td>{item.developer}</td>
                        <td>{item.login_install}</td>
                        <td>{item.equipment_location}</td>
                        <td>{item.poc_information}</td>
                        <td>{item.remarks}</td>
                        {canEdit && (
                          <td>
                            <button type="button" onClick={() => beginEdit(item)}>Edit</button>{" "}
                            <button type="button" onClick={() => void removeAssignment(item)}>Delete</button>
                          </td>
                        )}
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </section>

          {canEdit && (
            <form className="form-grid" onSubmit={handleAssignmentSave}>
              <h3 id="ics205b-assignment-editor" tabIndex={-1}>
                {editingAssignmentId ? "Edit IT assignment" : "Add IT assignment"}
              </h3>
              <label>
                Assignment
                <input value={draft.assignment} onChange={(event) => setField("assignment", event.target.value)} />
              </label>
              <label>
                IT Resource Type
                <input value={draft.it_resource_type} onChange={(event) => setField("it_resource_type", event.target.value)} />
              </label>
              <label>
                Name of Application or Resource
                <input value={draft.resource_name} onChange={(event) => setField("resource_name", event.target.value)} />
              </label>
              <label>
                Usage or Description
                <textarea value={draft.usage_description} onChange={(event) => setField("usage_description", event.target.value)} />
              </label>
              <label>
                Platform
                <input value={draft.platform} onChange={(event) => setField("platform", event.target.value)} />
              </label>
              <label>
                Developer
                <input value={draft.developer} onChange={(event) => setField("developer", event.target.value)} />
              </label>
              <label>
                Login/Install
                <textarea value={draft.login_install} onChange={(event) => setField("login_install", event.target.value)} />
              </label>
              <label>
                Equipment Location / Web Address, IP Address or SSID
                <textarea value={draft.equipment_location} onChange={(event) => setField("equipment_location", event.target.value)} />
              </label>
              <label>
                POC Information
                <textarea value={draft.poc_information} onChange={(event) => setField("poc_information", event.target.value)} />
              </label>
              <label>
                Remarks
                <textarea value={draft.remarks} onChange={(event) => setField("remarks", event.target.value)} />
              </label>
              <button type="submit" disabled={loading}>
                {editingAssignmentId ? "Save assignment" : "Add assignment"}
              </button>
              {editingAssignmentId && (
                <button
                  type="button"
                  onClick={() => {
                    setEditingAssignmentId(null);
                    setDraft({ ...EMPTY_ASSIGNMENT });
                  }}
                >
                  Cancel edit
                </button>
              )}
            </form>
          )}

          {canExport && (
            <div className="button-row" aria-label="ICS 205B exports">
              <button type="button" onClick={() => void exportForm("xlsx")} disabled={loading}>
                Export Excel
              </button>
              <button type="button" onClick={() => void exportForm("pdf")} disabled={loading}>
                Export PDF
              </button>
            </div>
          )}
        </>
      )}

      {loading && <p role="status">Working…</p>}
      {message && <p role="status">{message}</p>}
    </section>
  );
}
