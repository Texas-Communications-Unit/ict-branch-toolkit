import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  createIncident,
  createOperationalPeriod,
  archiveIncident,
  getCurrentUser,
  importChannelLibrary,
  listConventionalChannels,
  listIncidents,
  listTrunkedTalkgroups,
  login,
} from "./api";
import { BrandMark } from "./BrandMark";
import { MapShell } from "./MapShell";
import { PlanWorkspace } from "./PlanWorkspace";
import type {
  ConventionalChannel,
  CurrentUser,
  ImportResult,
  Incident,
  TrunkedTalkgroup,
} from "./types";

const syntheticImportExample = JSON.stringify(
  {
    source: {
      slug: "synthetic-p1-1",
      name: "Synthetic P1.1 Fixture",
      source_type: "synthetic",
      authoritative_url: "https://example.invalid/synthetic-p1-1",
    },
    release: {
      version: "SYN-1",
      released_on: "2026-07-22",
      effective_status: "effective",
      content_sha256: "0".repeat(64),
    },
    conventional_channels: [
      {
        identifier: "SYN-VHF-1",
        name: "Synthetic VHF Calling",
        band: "VHF",
        rx_frequency_hz: 155000000,
        tx_frequency_hz: 155000000,
        bandwidth_hz: 12500,
        mode: "analog_fm",
        rx_squelch: "CSQ",
        tx_squelch: "CSQ",
        restrictions: "Synthetic exercise use only",
        notes: "Not an assigned or authorized frequency",
        is_active: true,
      },
    ],
    trunked_talkgroups: [
      {
        identifier: "SYN-TG-1",
        name: "Synthetic Operations",
        system_name: "Synthetic Regional System",
        talkgroup_id: 65001,
        mode: "P25 Phase 2",
        restrictions: "Synthetic exercise use only",
        notes: "Not a real talkgroup",
        is_active: true,
      },
    ],
  },
  null,
  2,
);

export default function App() {
  const [authenticated, setAuthenticated] = useState(() =>
    Boolean(sessionStorage.getItem("ict-toolkit-token")),
  );
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [channels, setChannels] = useState<ConventionalChannel[]>([]);
  const [talkgroups, setTalkgroups] = useState<TrunkedTalkgroup[]>([]);
  const [resourceSearch, setResourceSearch] = useState("");
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [selectedIncident, setSelectedIncident] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const normalizedResourceSearch = resourceSearch.trim().toLocaleLowerCase();
  const visibleChannels = useMemo(
    () =>
      channels.filter((channel) =>
        [
          channel.identifier,
          channel.name,
          channel.channel_use,
          channel.band,
          channel.jurisdiction,
          channel.eligibility,
          channel.authorization,
          channel.restrictions,
          channel.notes,
          channel.source_section,
        ]
          .join(" ")
          .toLocaleLowerCase()
          .includes(normalizedResourceSearch),
      ),
    [channels, normalizedResourceSearch],
  );
  const visibleTalkgroups = useMemo(
    () =>
      talkgroups.filter((talkgroup) =>
        [
          talkgroup.identifier,
          talkgroup.name,
          talkgroup.system_name,
          talkgroup.eligibility,
          talkgroup.authorization,
          talkgroup.restrictions,
          talkgroup.notes,
          talkgroup.source_section,
        ]
          .join(" ")
          .toLocaleLowerCase()
          .includes(normalizedResourceSearch),
      ),
    [talkgroups, normalizedResourceSearch],
  );

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const user = await getCurrentUser();
      const [items, conventional, trunked] = await Promise.all([
        listIncidents(),
        listConventionalChannels(),
        listTrunkedTalkgroups(),
      ]);
      setCurrentUser(user);
      setIncidents(items);
      setChannels(conventional);
      setTalkgroups(trunked);
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

  async function handleArchive(incident: Incident) {
    if (
      !window.confirm(
        `Archive ${incident.name}? It will be retained in the audit history.`,
      )
    ) {
      return;
    }
    try {
      await archiveIncident(incident.id);
      setSelectedIncident("");
      await refresh();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Unable to archive incident.",
      );
    }
  }

  async function processImport(form: HTMLFormElement, dryRun: boolean) {
    const data = new FormData(form);
    try {
      const payload = JSON.parse(String(data.get("payload"))) as Record<
        string,
        unknown
      >;
      const result = await importChannelLibrary({
        ...payload,
        dry_run: dryRun,
      });
      setImportResult(result);
      setError("");
      if (!dryRun && result.valid) await refresh();
    } catch (caught) {
      setError(
        caught instanceof SyntaxError
          ? "Import JSON is not valid."
          : caught instanceof Error
            ? caught.message
            : "Unable to process the import.",
      );
    }
  }

  function handleImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void processImport(event.currentTarget, true);
  }

  const selected = incidents.find(
    (incident) => incident.id === selectedIncident,
  );
  const canCreateIncident =
    currentUser?.permissions.includes("incident.create") ?? false;
  const canCreatePeriod =
    selected?.permissions.includes("period.create") ?? false;

  if (!authenticated) {
    return (
      <main className="login-layout">
        <section className="login-card">
          <div className="login-identity">
            <BrandMark className="login-logo" />
            <div>
              <p className="eyebrow">Texas Communications Unit (TX-COMU)</p>
              <h1>ICT Branch Toolkit</h1>
              <p className="short-name">ICT Toolkit</p>
            </div>
          </div>
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
            Licensed under GNU AGPL v3.{" "}
            <a href="/third-party/maplibre-gl-LICENSE.txt">
              MapLibre and third-party notices
            </a>
          </p>
        </section>
      </main>
    );
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to planning workspace
      </a>
      <header className="app-header">
        <div className="app-identity">
          <BrandMark className="header-logo" />
          <div>
            <p className="eyebrow">Texas Communications Unit (TX-COMU)</p>
            <h1>ICT Branch Toolkit</h1>
            <p className="short-name">ICT Toolkit</p>
          </div>
        </div>
        <div className="identity-summary">
          <span>{currentUser?.display_name}</span>
          <div className="prototype-badge">
            P1.3 Prototype · {currentUser?.role}
          </div>
        </div>
      </header>
      {error && (
        <p role="alert" className="error banner">
          {error}
        </p>
      )}
      <main className="workspace" id="main-content" tabIndex={-1}>
        <section className="planning-panel" aria-labelledby="incidents-heading">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Current workspace</p>
              <h2 id="incidents-heading">Incidents</h2>
            </div>
            <span className="count">{incidents.length}</span>
          </div>
          {canCreateIncident && (
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
          )}
          {loading ? (
            <p role="status" aria-live="polite">
              Loading incidents…
            </p>
          ) : incidents.length === 0 ? (
            <p className="empty">
              No incidents yet. Create a synthetic incident to begin.
            </p>
          ) : (
            <div className="incident-list">
              {incidents.map((incident) => (
                <article key={incident.id} className="incident">
                  <button
                    className={
                      selectedIncident === incident.id
                        ? "incident-select selected"
                        : "incident-select"
                    }
                    type="button"
                    aria-pressed={selectedIncident === incident.id}
                    onClick={() => setSelectedIncident(incident.id)}
                  >
                    <span>
                      <strong>{incident.name}</strong>
                      <small>
                        {incident.incident_number || "No incident number"}
                      </small>
                    </span>
                    <span className="incident-status">{incident.status}</span>
                  </button>
                  {incident.permissions.includes("incident.archive") && (
                    <button
                      className="text-button"
                      type="button"
                      onClick={() => void handleArchive(incident)}
                    >
                      Archive {incident.name}
                    </button>
                  )}
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
          {canCreatePeriod && (
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
          )}
        </section>
        <PlanWorkspace incident={selected} />
        <MapShell incident={selected} />
        <section className="library-panel" aria-labelledby="library-heading">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Source-aware reference data</p>
              <h2 id="library-heading">Channel library</h2>
            </div>
            <span className="count">
              {visibleChannels.length + visibleTalkgroups.length}
            </span>
          </div>
          <label className="library-search">
            Search channels, uses, restrictions, or source details
            <input
              type="search"
              value={resourceSearch}
              onChange={(event) => setResourceSearch(event.target.value)}
              placeholder="Examples: VTAC33, medical, Texas, deployable"
            />
          </label>
          <div className="resource-grid">
            <div>
              <h3>Conventional channels</h3>
              {visibleChannels.length === 0 ? (
                <p className="empty">
                  {channels.length === 0
                    ? "No releases imported."
                    : "No conventional channels match this search."}
                </p>
              ) : (
                visibleChannels.map((channel) => (
                  <article className="resource-card" key={channel.id}>
                    <strong>
                      {channel.name} <small>({channel.identifier})</small>
                    </strong>
                    <span>
                      {(channel.rx_frequency_hz / 1_000_000).toFixed(6)} MHz ·{" "}
                      {channel.mode}
                    </span>
                    {channel.channel_use && <span>{channel.channel_use}</span>}
                    {channel.restrictions && (
                      <details>
                        <summary>Restrictions and use conditions</summary>
                        <p>{channel.restrictions}</p>
                      </details>
                    )}
                    <small>
                      {channel.release.source.name} · {channel.release.version}
                      {channel.source_pages
                        ? ` · NIFOG p. ${channel.source_pages}`
                        : ""}
                    </small>
                  </article>
                ))
              )}
            </div>
            <div>
              <h3>Trunked talkgroups</h3>
              {visibleTalkgroups.length === 0 ? (
                <p className="empty">
                  {talkgroups.length === 0
                    ? "No releases imported."
                    : "No trunked talkgroups match this search."}
                </p>
              ) : (
                visibleTalkgroups.map((talkgroup) => (
                  <article className="resource-card" key={talkgroup.id}>
                    <strong>
                      {talkgroup.name} <small>({talkgroup.identifier})</small>
                    </strong>
                    <span>
                      {talkgroup.system_name} · TG {talkgroup.talkgroup_id}
                    </span>
                    {talkgroup.restrictions && (
                      <details>
                        <summary>Restrictions and use conditions</summary>
                        <p>{talkgroup.restrictions}</p>
                      </details>
                    )}
                    <small>
                      {talkgroup.release.source.name} ·{" "}
                      {talkgroup.release.version}
                      {talkgroup.source_pages
                        ? ` · NIFOG p. ${talkgroup.source_pages}`
                        : ""}
                    </small>
                  </article>
                ))
              )}
            </div>
          </div>
          {currentUser?.permissions.includes("library.import") && (
            <form className="import-panel" onSubmit={handleImport}>
              <h3>Administrator import</h3>
              <p>
                Validate first. CISA releases cannot be applied until their
                exact source, version, URL, and digest are approved in server
                configuration.
              </p>
              <label>
                Import JSON
                <textarea
                  name="payload"
                  defaultValue={syntheticImportExample}
                  rows={12}
                  required
                />
              </label>
              <div className="button-row">
                <button type="submit">Validate dry run</button>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={(event) => {
                    if (event.currentTarget.form)
                      void processImport(event.currentTarget.form, false);
                  }}
                >
                  Apply approved import
                </button>
              </div>
              {importResult && (
                <div
                  className={
                    importResult.valid ? "import-result valid" : "import-result"
                  }
                  role="status"
                >
                  {importResult.valid
                    ? "Validation passed."
                    : "Validation failed."}
                  {importResult.approval_required &&
                    " Human approval is still required."}
                  {importResult.errors.map((item) => (
                    <p key={`${item.path}-${item.code}`}>
                      {item.path}: {item.message}
                    </p>
                  ))}
                </div>
              )}
            </form>
          )}
        </section>
      </main>
      <footer>
        <div>
          <p>
            Planning outputs are not frequency coordination approvals, spectrum
            authorizations, propagation studies, or guarantees of coverage.
          </p>
          <p className="footer-attribution">
            Originally developed by the Texas Communications Unit (TX-COMU). ICT
            Branch Toolkit software is licensed under GNU AGPL v3. TX-COMU
            names, logos, and identifying marks remain organizational brand
            assets and are not relicensed under the software license.
          </p>
        </div>
        <div className="footer-links">
          <a
            href="https://github.com/Texas-Communications-Unit/ict-branch-toolkit"
            aria-label="View ICT Branch Toolkit source code on GitHub"
          >
            View source code
          </a>
          <a href="/third-party/maplibre-gl-LICENSE.txt">
            MapLibre and third-party notices
          </a>
        </div>
      </footer>
    </div>
  );
}
