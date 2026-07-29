import {
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  createExtensionExecution,
  disableExtension,
  downloadExtensionExecution,
  enableExtension,
  installExtension,
  listExtensionCatalog,
  listExtensionExecutions,
  listPlans,
} from "./api";
import type {
  CurrentUser,
  ExtensionCatalogEntry,
  ExtensionExecution,
  ICS205Plan,
  Incident,
} from "./types";

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

function SummaryResult({ execution }: { execution: ExtensionExecution }) {
  const result = execution.result_snapshot;
  if (execution.status === "failed") {
    return <p>{execution.failure_message}</p>;
  }
  const summary =
    typeof result.summary === "object" && result.summary !== null
      ? (result.summary as Record<string, unknown>)
      : result;
  const rows = Array.isArray(result.rows) ? result.rows : [];
  return (
    <>
      <dl className="extension-result-summary">
        <div>
          <dt>State</dt>
          <dd>{String(summary.readiness_state ?? "Recorded")}</dd>
        </div>
        <div>
          <dt>Assignments</dt>
          <dd>{String(summary.assignment_count ?? "Not reported")}</dd>
        </div>
        <div>
          <dt>Missing frequencies</dt>
          <dd>{String(summary.missing_frequency_count ?? "Not reported")}</dd>
        </div>
        <div>
          <dt>Classification</dt>
          <dd>{execution.output_classification.replace("_", " ")}</dd>
        </div>
      </dl>
      {rows.length > 0 && (
        <div
          className="table-scroll"
          role="region"
          aria-label="Synthetic readiness report rows"
        >
          <table>
            <caption>Synthetic assignment counts by function</caption>
            <thead>
              <tr>
                <th scope="col">Function</th>
                <th scope="col">Assignment count</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => {
                const cells = Array.isArray(row) ? row : [];
                return (
                  <tr key={`${String(cells[0])}-${index}`}>
                    <th scope="row">{String(cells[0] ?? "Unspecified")}</th>
                    <td>{String(cells[1] ?? "0")}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

export function ExtensionWorkspace({
  incident,
  currentUser,
}: {
  incident?: Incident;
  currentUser: CurrentUser | null;
}) {
  const [catalog, setCatalog] = useState<ExtensionCatalogEntry[]>([]);
  const [plans, setPlans] = useState<ICS205Plan[]>([]);
  const [executions, setExecutions] = useState<ExtensionExecution[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const canAdmin =
    currentUser?.permissions.includes("extension.admin") ?? false;
  const canRun = incident?.permissions.includes("extension.run") ?? false;
  const activeExtension = catalog.find(
    (entry) => entry.installed && entry.enabled && entry.compatible,
  );
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

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [nextCatalog, nextPlans, nextExecutions] = await Promise.all([
        listExtensionCatalog(),
        incident ? listPlans() : Promise.resolve([]),
        incident ? listExtensionExecutions(incident.id) : Promise.resolve([]),
      ]);
      setCatalog(nextCatalog);
      setPlans(nextPlans);
      setExecutions(nextExecutions);
      setError("");
    } catch (loadError) {
      setError(errorMessage(loadError, "Unable to load planning extensions."));
    } finally {
      setLoading(false);
    }
  }, [incident]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function manage(
    entry: ExtensionCatalogEntry,
    action: "install" | "enable" | "disable",
  ) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      if (action === "install") {
        await installExtension(
          entry.manifest.key,
          entry.manifest.contract_version,
        );
      } else if (action === "enable") {
        await enableExtension(entry.manifest.key);
      } else {
        await disableExtension(entry.manifest.key);
      }
      setMessage(
        `${entry.manifest.name} ${
          action === "install" ? "installed disabled" : `${action}d`
        }.`,
      );
      await refresh();
    } catch (managementError) {
      setError(
        errorMessage(managementError, `Unable to ${action} the extension.`),
      );
    } finally {
      setBusy(false);
    }
  }

  async function runExtension(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!incident || !activeExtension || !canRun) return;
    const data = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const execution = await createExtensionExecution({
        extension_key: activeExtension.manifest.key,
        contract_version: activeExtension.manifest.contract_version,
        capability: String(data.get("capability")),
        incident: incident.id,
        source_revision: String(data.get("source_revision")),
        inputs: {
          minimum_assignment_count: Number(
            data.get("minimum_assignment_count"),
          ),
        },
      });
      setExecutions(await listExtensionExecutions(incident.id));
      setMessage(
        execution.status === "complete"
          ? "Synthetic extension output recorded."
          : execution.failure_message,
      );
    } catch (runError) {
      setError(errorMessage(runError, "Unable to run the planning extension."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="extension-panel" aria-labelledby="extensions-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Governed optional capabilities</p>
          <h2 id="extensions-heading">ICT planning tools and reports</h2>
        </div>
        <span className="count">{executions.length}</span>
      </div>
      <p className="panel-intro">
        Extensions are code-defined, versioned, and disabled until an
        administrator installs and enables them. Arbitrary uploaded executable
        code is not supported.
      </p>

      {loading ? (
        <p role="status" aria-live="polite">
          Loading planning extensions…
        </p>
      ) : (
        <>
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          {message && (
            <p className="extension-message" role="status" aria-live="polite">
              {message}
            </p>
          )}
          <div className="extension-catalog">
            {catalog.map((entry) => (
              <article className="extension-card" key={entry.manifest.key}>
                <div className="extension-card-heading">
                  <div>
                    <h3>{entry.manifest.name}</h3>
                    <span>
                      Version {entry.manifest.version} · contract{" "}
                      {entry.manifest.contract_version}
                    </span>
                  </div>
                  <span
                    className={`status ${entry.enabled ? "approved" : "draft"}`}
                  >
                    {entry.enabled ? "enabled" : "disabled"}
                  </span>
                </div>
                <p>{entry.manifest.description}</p>
                <p className="extension-operator-message">
                  {entry.operator_message}
                </p>
                <details>
                  <summary>Contract, governance, and retention</summary>
                  <dl className="extension-contract">
                    <div>
                      <dt>Capabilities</dt>
                      <dd>
                        {entry.manifest.capabilities
                          .map(
                            (capability) =>
                              `${capability.name} (${capability.kind})`,
                          )
                          .join("; ")}
                      </dd>
                    </div>
                    <div>
                      <dt>Source records</dt>
                      <dd>{entry.manifest.source_records.join(" ")}</dd>
                    </div>
                    <div>
                      <dt>Approval</dt>
                      <dd>{entry.manifest.approval_requirements}</dd>
                    </div>
                    <div>
                      <dt>Sensitivity</dt>
                      <dd>{entry.manifest.sensitivity.replaceAll("_", " ")}</dd>
                    </div>
                    <div>
                      <dt>Retention</dt>
                      <dd>{entry.manifest.retention}</dd>
                    </div>
                    <div>
                      <dt>Failure boundary</dt>
                      <dd>{entry.manifest.failure_isolation}</dd>
                    </div>
                  </dl>
                </details>
                {canAdmin && (
                  <div className="button-row">
                    {!entry.installed ? (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void manage(entry, "install")}
                      >
                        Install disabled
                      </button>
                    ) : !entry.compatible ? (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void manage(entry, "install")}
                      >
                        Reinstall registered version disabled
                      </button>
                    ) : entry.enabled ? (
                      <button
                        className="secondary-button"
                        type="button"
                        disabled={busy}
                        onClick={() => void manage(entry, "disable")}
                      >
                        Disable extension
                      </button>
                    ) : (
                      <button
                        type="button"
                        disabled={busy || !entry.compatible}
                        onClick={() => void manage(entry, "enable")}
                      >
                        Enable compatible version
                      </button>
                    )}
                  </div>
                )}
              </article>
            ))}
          </div>

          {!incident ? (
            <p className="empty">
              Select an incident to run enabled tools or view retained reports.
            </p>
          ) : activeExtension && canRun ? (
            <form className="extension-run-form" onSubmit={runExtension}>
              <h3>Run the synthetic contract example</h3>
              <p>
                This example reads only approved ICS-205 assignment metadata and
                produces non-operational decision-support evidence.
              </p>
              <label>
                Capability
                <select name="capability" required>
                  {activeExtension.manifest.capabilities.map((capability) => (
                    <option key={capability.id} value={capability.id}>
                      {capability.name} ({capability.kind})
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Approved ICS-205 revision
                <select
                  name="source_revision"
                  required
                  disabled={approvedRevisions.length === 0}
                >
                  <option value="">Select approved revision</option>
                  {approvedRevisions.map(({ plan, revision }) => (
                    <option key={revision.id} value={revision.id}>
                      {plan.title} · revision {revision.number}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Minimum assignment count
                <input
                  name="minimum_assignment_count"
                  type="number"
                  min={1}
                  max={1000}
                  defaultValue={1}
                  required
                />
              </label>
              <button
                type="submit"
                disabled={busy || approvedRevisions.length === 0}
              >
                Run synthetic extension
              </button>
            </form>
          ) : (
            <p className="empty">
              No compatible planning extension is currently installed and
              enabled for this incident.
            </p>
          )}

          {incident && executions.length > 0 && (
            <div className="extension-executions">
              <h3>Retained extension output</h3>
              {executions.map((execution) => (
                <article className="extension-output" key={execution.id}>
                  <div className="extension-card-heading">
                    <div>
                      <h4>
                        {execution.capability.replaceAll("-", " ")} · revision{" "}
                        {execution.source_revision_number}
                      </h4>
                      <span>
                        {execution.extension_version} ·{" "}
                        {new Date(execution.created_at).toLocaleString()}
                      </span>
                    </div>
                    <span
                      className={`status ${
                        execution.status === "complete"
                          ? "approved"
                          : "excluded"
                      }`}
                    >
                      {execution.status}
                    </span>
                  </div>
                  <SummaryResult execution={execution} />
                  <details>
                    <summary>Evidence digests</summary>
                    <dl className="extension-digests">
                      <div>
                        <dt>Input SHA-256</dt>
                        <dd>{execution.input_sha256}</dd>
                      </div>
                      <div>
                        <dt>Result SHA-256</dt>
                        <dd>{execution.result_sha256}</dd>
                      </div>
                    </dl>
                  </details>
                  {execution.status === "complete" && (
                    <button
                      className="secondary-button"
                      type="button"
                      onClick={() =>
                        void downloadExtensionExecution(execution).catch(
                          (downloadError: unknown) =>
                            setError(
                              errorMessage(
                                downloadError,
                                "Unable to download extension output.",
                              ),
                            ),
                        )
                      }
                    >
                      Download deterministic JSON
                    </button>
                  )}
                </article>
              ))}
            </div>
          )}
        </>
      )}
    </section>
  );
}
