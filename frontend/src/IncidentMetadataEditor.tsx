import { type FormEvent, useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";

import { listIncidents } from "./api";
import {
  IncidentEditApiError,
  updateIncidentName,
  updateOperationalPeriod,
} from "./incidentEditingApi";
import type { Incident, OperationalPeriod } from "./types";

function toLocalDateTime(value: string) {
  const date = new Date(value);
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

function validationMessage(error: unknown) {
  if (!(error instanceof IncidentEditApiError)) {
    return error instanceof Error ? error.message : "Unable to save metadata.";
  }
  if (error.status === 403) {
    return "Your incident role does not allow this metadata change.";
  }
  if (typeof error.data === "object" && error.data !== null) {
    const messages = Object.entries(error.data as Record<string, unknown>).flatMap(
      ([field, value]) => {
        const values = Array.isArray(value) ? value : [value];
        return values
          .filter((item): item is string => typeof item === "string")
          .map((item) => `${field.replaceAll("_", " ")}: ${item}`);
      },
    );
    if (messages.length) return messages.join(" ");
  }
  return error.message || "Unable to save metadata.";
}

function updatePeriodInIncident(
  incident: Incident,
  updated: OperationalPeriod,
): Incident {
  return {
    ...incident,
    operational_periods: incident.operational_periods.map((period) =>
      period.id === updated.id ? updated : period,
    ),
  };
}

export function IncidentMetadataEditor() {
  const [target, setTarget] = useState<HTMLElement | null>(null);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [incidentId, setIncidentId] = useState("");
  const [periodId, setPeriodId] = useState("");
  const [incidentName, setIncidentName] = useState("");
  const [periodName, setPeriodName] = useState("");
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const findTarget = () => {
      const heading = document.getElementById("incidents-heading");
      setTarget(heading?.closest<HTMLElement>(".planning-panel") ?? null);
    };
    findTarget();
    const observer = new MutationObserver(findTarget);
    observer.observe(document.getElementById("root") ?? document.body, {
      childList: true,
      subtree: true,
    });
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!target) return;
    let active = true;
    void listIncidents()
      .then((result) => {
        if (!active) return;
        setIncidents(result);
        setIncidentId((current) =>
          result.some((incident) => incident.id === current)
            ? current
            : (result[0]?.id ?? ""),
        );
      })
      .catch((caught) => {
        if (active) setError(validationMessage(caught));
      });
    return () => {
      active = false;
    };
  }, [target]);

  const selectedIncident = useMemo(
    () => incidents.find((incident) => incident.id === incidentId),
    [incidentId, incidents],
  );
  const selectedPeriod = useMemo(
    () =>
      selectedIncident?.operational_periods.find(
        (period) => period.id === periodId,
      ),
    [periodId, selectedIncident],
  );
  const canEditIncident =
    selectedIncident?.permissions.includes("incident.change") ?? false;
  const canEditPeriod =
    selectedIncident?.permissions.includes("period.change") ?? false;
  const hasAnyEditableIncident = incidents.some(
    (incident) =>
      incident.permissions.includes("incident.change") ||
      incident.permissions.includes("period.change"),
  );

  useEffect(() => {
    setIncidentName(selectedIncident?.name ?? "");
    const periods = selectedIncident?.operational_periods ?? [];
    setPeriodId((current) =>
      periods.some((period) => period.id === current)
        ? current
        : (periods[0]?.id ?? ""),
    );
    setStatus("");
    setError("");
  }, [selectedIncident]);

  useEffect(() => {
    setPeriodName(selectedPeriod?.name ?? "");
    setStartsAt(selectedPeriod ? toLocalDateTime(selectedPeriod.starts_at) : "");
    setEndsAt(selectedPeriod ? toLocalDateTime(selectedPeriod.ends_at) : "");
  }, [selectedPeriod]);

  async function saveIncident(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedIncident || !canEditIncident) return;
    setSaving(true);
    setError("");
    setStatus("");
    try {
      const updated = await updateIncidentName(selectedIncident.id, incidentName);
      setIncidents((current) =>
        current.map((incident) =>
          incident.id === updated.id ? updated : incident,
        ),
      );
      setIncidentName(updated.name);
      setStatus(`Incident name saved as ${updated.name}.`);
      window.dispatchEvent(new Event("ict-incidents-updated"));
    } catch (caught) {
      setError(validationMessage(caught));
    } finally {
      setSaving(false);
    }
  }

  async function savePeriod(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedIncident || !selectedPeriod || !canEditPeriod) return;
    setSaving(true);
    setError("");
    setStatus("");
    try {
      const updated = await updateOperationalPeriod(selectedPeriod.id, {
        name: periodName,
        starts_at: new Date(startsAt).toISOString(),
        ends_at: new Date(endsAt).toISOString(),
      });
      setIncidents((current) =>
        current.map((incident) =>
          incident.id === selectedIncident.id
            ? updatePeriodInIncident(incident, updated)
            : incident,
        ),
      );
      setStatus(`Operational period ${updated.name} saved.`);
      window.dispatchEvent(new Event("ict-incidents-updated"));
    } catch (caught) {
      setError(validationMessage(caught));
    } finally {
      setSaving(false);
    }
  }

  if (!target || incidents.length === 0) return null;

  return createPortal(
    <section
      className="incident-metadata-editor"
      aria-labelledby="incident-metadata-editor-heading"
    >
      <div className="section-heading">
        <div>
          <p className="eyebrow">Lifecycle corrections</p>
          <h3 id="incident-metadata-editor-heading">Edit incident metadata</h3>
        </div>
      </div>
      {!hasAnyEditableIncident ? (
        <p className="empty">
          Your incident role is read-only for incident and operational-period
          metadata.
        </p>
      ) : (
        <>
          <label>
            Incident to edit
            <select
              value={incidentId}
              onChange={(event) => setIncidentId(event.target.value)}
            >
              {incidents.map((incident) => (
                <option key={incident.id} value={incident.id}>
                  {incident.name}
                </option>
              ))}
            </select>
          </label>
          {canEditIncident && selectedIncident && (
            <form className="compact-form" onSubmit={saveIncident}>
              <label>
                Incident name
                <input
                  value={incidentName}
                  onChange={(event) => setIncidentName(event.target.value)}
                  maxLength={200}
                  required
                  aria-describedby="incident-edit-history-note"
                />
              </label>
              <div className="button-row">
                <button type="submit" disabled={saving}>
                  {saving ? "Saving…" : "Save incident name"}
                </button>
                <button
                  type="button"
                  className="secondary-button"
                  disabled={saving}
                  onClick={() => {
                    setIncidentName(selectedIncident.name);
                    setError("");
                    setStatus("Incident edit canceled; no changes were saved.");
                  }}
                >
                  Cancel
                </button>
              </div>
            </form>
          )}
          {canEditPeriod && selectedIncident && (
            <div className="period-edit-workspace">
              {selectedIncident.operational_periods.length === 0 ? (
                <p className="empty">This incident has no operational periods.</p>
              ) : (
                <form className="compact-form" onSubmit={savePeriod}>
                  <label>
                    Operational period
                    <select
                      value={periodId}
                      onChange={(event) => setPeriodId(event.target.value)}
                    >
                      {selectedIncident.operational_periods.map((period) => (
                        <option key={period.id} value={period.id}>
                          {period.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Period name
                    <input
                      value={periodName}
                      onChange={(event) => setPeriodName(event.target.value)}
                      maxLength={120}
                      required
                    />
                  </label>
                  <label>
                    Starts
                    <input
                      type="datetime-local"
                      value={startsAt}
                      onChange={(event) => setStartsAt(event.target.value)}
                      required
                    />
                  </label>
                  <label>
                    Ends
                    <input
                      type="datetime-local"
                      value={endsAt}
                      onChange={(event) => setEndsAt(event.target.value)}
                      required
                    />
                  </label>
                  <div className="button-row">
                    <button type="submit" disabled={saving}>
                      {saving ? "Saving…" : "Save operational period"}
                    </button>
                    <button
                      type="button"
                      className="secondary-button"
                      disabled={saving}
                      onClick={() => {
                        if (!selectedPeriod) return;
                        setPeriodName(selectedPeriod.name);
                        setStartsAt(toLocalDateTime(selectedPeriod.starts_at));
                        setEndsAt(toLocalDateTime(selectedPeriod.ends_at));
                        setError("");
                        setStatus(
                          "Operational-period edit canceled; no changes were saved.",
                        );
                      }}
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              )}
            </div>
          )}
        </>
      )}
      <p id="incident-edit-history-note" className="map-note">
        Corrections affect current lifecycle metadata only. Existing approved plan
        revisions and previously generated historical artifacts are not rewritten.
      </p>
      {status && (
        <p role="status" aria-live="polite" className="site-message">
          {status}
        </p>
      )}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </section>,
    target,
  );
}
