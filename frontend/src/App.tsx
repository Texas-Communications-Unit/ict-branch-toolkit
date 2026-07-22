import { FormEvent, useCallback, useEffect, useState } from "react";

import {
  createIncident,
  createOperationalPeriod,
  listIncidents,
  login,
} from "./api";
import { MapShell } from "./MapShell";
import type { Incident } from "./types";

export default function App() {
  const [authenticated, setAuthenticated] = useState(() =>
    Boolean(sessionStorage.getItem("ict-toolkit-token")),
  );
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selectedIncident, setSelectedIncident] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const items = await listIncidents();
      setIncidents(items);
      setSelectedIncident((current) => current || items[0]?.id || "");
      setError("");
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Unable to load incidents.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (authenticated) void refresh();
  }, [authenticated, refresh]);

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    try {
      await login(String(data.get("username")), String(data.get("password")));
      setAuthenticated(true);
      setError("");
    } catch {
      setError("Sign-in failed. Verify the local administrator credentials.");
    }
  }

  async function handleIncident(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    try {
      const incident = await createIncident(
        String(data.get("name")),
        String(data.get("number")),
      );
      form.reset();
      await refresh();
      setSelectedIncident(incident.id);
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Unable to create incident.",
      );
    }
  }

  async function handlePeriod(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    try {
      await createOperationalPeriod(
        selectedIncident,
        String(data.get("periodName")),
        String(data.get("startsAt")),
        String(data.get("endsAt")),
      );
      form.reset();
      await refresh();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Unable to create operational period.",
      );
    }
  }

  if (!authenticated) {
    return (
      <main className="login-layout">
        <section className="login-card">
          <p className="eyebrow">Operational planning prototype</p>
          <h1>ICT Branch Toolkit</h1>
          <p>
            Sign in with the local development administrator configured for this
            installation.
          </p>
          <form onSubmit={handleLogin}>
            <label>
              Username
              <input name="username" autoComplete="username" required />
            </label>
            <label>
              Password
              <input
                name="password"
                type="password"
                autoComplete="current-password"
                required
              />
            </label>
            <button type="submit">Sign in</button>
          </form>
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
          <p className="legal">
            Originally developed by the Texas Communications Unit (TX-COMU).
            Licensed under GNU AGPL v3.
          </p>
        </section>
      </main>
    );
  }

  return (
    <div className="app-shell">
      <header>
        <div>
          <p className="eyebrow">Texas Communications Unit</p>
          <h1>ICT Branch Toolkit</h1>
        </div>
        <div className="prototype-badge">P1.0 Prototype</div>
      </header>
      {error && (
        <p role="alert" className="error banner">
          {error}
        </p>
      )}
      <main className="workspace">
        <section className="planning-panel" aria-labelledby="incidents-heading">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Current workspace</p>
              <h2 id="incidents-heading">Incidents</h2>
            </div>
            <span className="count">{incidents.length}</span>
          </div>
          <form className="compact-form" onSubmit={handleIncident}>
            <label>
              Incident name
              <input name="name" placeholder="Synthetic exercise" required />
            </label>
            <label>
              Incident number
              <input name="number" placeholder="SYN-001" />
            </label>
            <button type="submit">Create incident</button>
          </form>
          {loading ? (
            <p>Loading incidents…</p>
          ) : incidents.length === 0 ? (
            <p className="empty">
              No incidents yet. Create a synthetic incident to begin.
            </p>
          ) : (
            <div className="incident-list">
              {incidents.map((incident) => (
                <article
                  key={incident.id}
                  className={
                    selectedIncident === incident.id
                      ? "incident selected"
                      : "incident"
                  }
                  onClick={() => setSelectedIncident(incident.id)}
                >
                  <div>
                    <h3>{incident.name}</h3>
                    <p>{incident.incident_number || "No incident number"}</p>
                  </div>
                  <span>{incident.status}</span>
                  {incident.operational_periods.map((period) => (
                    <p className="period" key={period.id}>
                      {period.name}:{" "}
                      {new Date(period.starts_at).toLocaleString()} –{" "}
                      {new Date(period.ends_at).toLocaleString()}
                    </p>
                  ))}
                </article>
              ))}
            </div>
          )}
          <form className="compact-form period-form" onSubmit={handlePeriod}>
            <h3>Add operational period</h3>
            <label>
              Incident
              <select
                value={selectedIncident}
                onChange={(event) => setSelectedIncident(event.target.value)}
                required
              >
                <option value="">Select incident</option>
                {incidents.map((incident) => (
                  <option key={incident.id} value={incident.id}>
                    {incident.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Period name
              <input
                name="periodName"
                placeholder="Operational Period 1"
                required
              />
            </label>
            <label>
              Starts
              <input name="startsAt" type="datetime-local" required />
            </label>
            <label>
              Ends
              <input name="endsAt" type="datetime-local" required />
            </label>
            <button type="submit" disabled={!selectedIncident}>
              Add period
            </button>
          </form>
        </section>
        <MapShell />
      </main>
      <footer>
        <p>
          Planning outputs are not frequency coordination approvals, spectrum
          authorizations, propagation studies, or guarantees of coverage.
        </p>
        <a href="https://github.com/Texas-Communications-Unit/ict-branch-toolkit">
          Source code
        </a>
      </footer>
    </div>
  );
}
