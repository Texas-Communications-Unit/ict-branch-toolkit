import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  createOfflinePackage,
  getOfflineStatus,
  getOfflineSupportBundle,
  listConventionalChannels,
  listOfflinePackages,
  listPlans,
  listRadioSites,
  listTerrainAnalyses,
  listTrunkedTalkgroups,
  lockOfflinePackage,
  purgeOfflinePackage,
  resolveOfflineConflict,
  synchronizeOfflinePackage,
  unlockOfflinePackage,
} from "./api";
import {
  applySynchronizationResult,
  cancelPendingMutation,
  createLocalSupportBundle,
  listLocalPackageMetadata,
  purgeExpiredLocalPackages,
  purgeLocalPackage,
  queueOfflineMutation,
  removeResolvedMutation,
  savePackageToDevice,
  unlockLocalPackage,
  type EncryptedOfflineEnvelope,
  type OfflineVault,
} from "./offlineStore";
import {
  activateOfflineUpdate,
  checkForOfflineUpdate,
  clearOfflineRuntimeCaches,
  SERVICE_WORKER_UPDATE_EVENT,
} from "./serviceWorker";
import type {
  ICS205Plan,
  Incident,
  OfflineMutation,
  OfflinePackageSummary,
  OfflineStatus,
  PlanAssignment,
  RadioSite,
  ResourceRelease,
  TerrainAnalysis,
} from "./types";

interface OfflineWorkspaceProps {
  incident?: Incident;
}

function deviceId(): string {
  const key = "ict-toolkit-offline-device-id";
  const current = localStorage.getItem(key);
  if (current) return current;
  const created = crypto.randomUUID();
  localStorage.setItem(key, created);
  return created;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} bytes`;
  if (bytes < 1024 * 1024) return `${Math.ceil(bytes / 1024)} KiB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MiB`;
}

function downloadJson(filename: string, value: unknown): void {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], {
      type: "application/json",
    }),
  );
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function mutationSummary(mutation: OfflineMutation): string {
  const label = mutation.operation.replace(".", " ");
  const status = mutation.sync_status ?? "pending";
  return `Sequence ${mutation.sequence}: ${label} (${status})`;
}

export function OfflineWorkspace({ incident }: OfflineWorkspaceProps) {
  const [capability, setCapability] = useState<OfflineStatus | null>(null);
  const [queueOperation, setQueueOperation] =
    useState<OfflineMutation["operation"]>("revision.update");
  const [plans, setPlans] = useState<ICS205Plan[]>([]);
  const [sites, setSites] = useState<RadioSite[]>([]);
  const [terrain, setTerrain] = useState<TerrainAnalysis[]>([]);
  const [releases, setReleases] = useState<ResourceRelease[]>([]);
  const [packages, setPackages] = useState<OfflinePackageSummary[]>([]);
  const [localPackages, setLocalPackages] = useState<
    EncryptedOfflineEnvelope[]
  >([]);
  const [selectedRevisions, setSelectedRevisions] = useState<string[]>([]);
  const [selectedReleases, setSelectedReleases] = useState<string[]>([]);
  const [selectedSites, setSelectedSites] = useState<string[]>([]);
  const [selectedTerrain, setSelectedTerrain] = useState<string[]>([]);
  const [includeMap, setIncludeMap] = useState(false);
  const [passphrase, setPassphrase] = useState("");
  const [vault, setVault] = useState<OfflineVault | null>(null);
  const [online, setOnline] = useState(navigator.onLine);
  const [updateReady, setUpdateReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(
    navigator.onLine
      ? ""
      : "Network connection unavailable. Only encrypted, explicitly packaged work remains available.",
  );
  const [error, setError] = useState("");

  const revisions = useMemo(
    () =>
      plans
        .filter((plan) => plan.incident === incident?.id)
        .flatMap((plan) =>
          plan.revisions.map((revision) => ({
            ...revision,
            planTitle: plan.title,
          })),
        ),
    [incident?.id, plans],
  );

  const selectedServerPackage = useMemo(
    () => packages.find((item) => item.id === vault?.package.id),
    [packages, vault?.package.id],
  );

  const refreshLocal = useCallback(async () => {
    setLocalPackages(await listLocalPackageMetadata());
  }, []);

  const refresh = useCallback(async () => {
    let localError = "";
    try {
      const purgedCount = await purgeExpiredLocalPackages();
      if (purgedCount > 0) {
        setMessage(
          `${purgedCount} expired encrypted package${purgedCount === 1 ? "" : "s"} purged from this device.`,
        );
      }
      await refreshLocal();
    } catch (caught) {
      localError =
        caught instanceof Error
          ? caught.message
          : "Unable to load encrypted packages from this device.";
    }
    try {
      const status = await getOfflineStatus();
      setCapability(status);
      if (!incident) {
        setPlans([]);
        setSites([]);
        setTerrain([]);
        setReleases([]);
        setPackages([]);
        return;
      }
      const [
        planItems,
        siteItems,
        terrainPage,
        conventional,
        trunked,
        packageItems,
      ] = await Promise.all([
        listPlans(),
        listRadioSites(incident.id),
        listTerrainAnalyses(incident.id),
        listConventionalChannels(),
        listTrunkedTalkgroups(),
        listOfflinePackages(incident.id),
      ]);
      const releaseById = new Map<string, ResourceRelease>();
      for (const item of [...conventional, ...trunked]) {
        releaseById.set(item.release.id, item.release);
      }
      setPlans(planItems);
      setSites(siteItems);
      setTerrain(terrainPage.results);
      setReleases([...releaseById.values()]);
      setPackages(packageItems);
      setSelectedRevisions((current) =>
        current.length > 0
          ? current
          : planItems
              .filter((plan) => plan.incident === incident.id)
              .flatMap((plan) => plan.revisions)
              .filter((revision) => revision.status === "draft")
              .slice(0, 1)
              .map((revision) => revision.id),
      );
      setError(localError);
    } catch (caught) {
      const serverError =
        caught instanceof Error
          ? caught.message
          : "Unable to load connected offline controls.";
      setError(
        localError
          ? `${localError} Connected controls also failed: ${serverError}`
          : serverError,
      );
    }
  }, [incident, refreshLocal]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (selectedSites.length === 0) setIncludeMap(false);
  }, [selectedSites.length]);

  useEffect(() => {
    const handleOnline = () => {
      setOnline(true);
      setMessage(
        "Connection restored. Review pending changes before synchronizing.",
      );
      void refresh();
    };
    const handleOffline = () => {
      setOnline(false);
      setMessage(
        "Network connection lost. Only encrypted, explicitly packaged work remains available.",
      );
    };
    const handleUpdate = () => setUpdateReady(true);
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    window.addEventListener(SERVICE_WORKER_UPDATE_EVENT, handleUpdate);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
      window.removeEventListener(SERVICE_WORKER_UPDATE_EVENT, handleUpdate);
    };
  }, [refresh]);

  function toggle(
    value: string,
    values: string[],
    setter: (next: string[]) => void,
  ) {
    setter(
      values.includes(value)
        ? values.filter((item) => item !== value)
        : [...values, value],
    );
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!incident || !capability?.enabled) return;
    if (passphrase.length < 12) {
      setError("Use an offline passphrase of at least 12 characters.");
      return;
    }
    setBusy(true);
    try {
      const form = new FormData(event.currentTarget);
      const created = await createOfflinePackage({
        incident: incident.id,
        device_id: deviceId(),
        expires_in_hours: Number(form.get("expires_in_hours")),
        selection: {
          revision_ids: selectedRevisions,
          resource_release_ids: selectedReleases,
          site_ids: selectedSites,
          terrain_analysis_ids: selectedTerrain,
          attachment_ids: [],
          include_map: includeMap,
        },
      });
      let saved: OfflineVault;
      try {
        saved = await savePackageToDevice(created, passphrase);
      } catch (storageError) {
        let serverState =
          "The server package was locked because the device copy was not saved.";
        try {
          await lockOfflinePackage(created.id);
        } catch {
          serverState =
            "The server package could not be locked; reconnect and lock or purge it before continuing.";
        }
        const detail =
          storageError instanceof Error
            ? storageError.message
            : "The device copy could not be saved.";
        throw new Error(`${detail} ${serverState}`, { cause: storageError });
      }
      setVault(saved);
      setMessage(
        "Package encrypted on this device. The passphrase is not stored and cannot be recovered.",
      );
      setError("");
      await refresh();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Unable to create the offline package.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleUnlock(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const packageId = String(form.get("package_id"));
    setBusy(true);
    try {
      const unlocked = await unlockLocalPackage(packageId, passphrase);
      const serverPackage = packages.find((item) => item.id === packageId);
      if (serverPackage?.current_status === "locked" && online) {
        await unlockOfflinePackage(packageId);
      }
      setVault(unlocked);
      setMessage("Encrypted package unlocked for this browser session.");
      setError("");
      await refresh();
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Unable to unlock package.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleQueue(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!vault) return;
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const revisionId = String(form.get("revision_id"));
    const assignmentId = String(form.get("assignment_id") || "");
    const revision = vault.package.payload_snapshot.revisions?.find(
      (item) => item.id === revisionId,
    );
    if (!revision || revision.status !== "draft") {
      setError("Only a packaged draft revision can receive offline changes.");
      return;
    }
    const assignment = revision.assignments.find(
      (item) => item.id === assignmentId,
    );
    const assignmentRequired =
      queueOperation === "assignment.update" ||
      queueOperation === "assignment.delete";
    if (assignmentRequired && !assignmentId) {
      setError("Select an assignment for this offline operation.");
      return;
    }
    if (assignmentId && !assignment) {
      setError("The selected assignment does not belong to that revision.");
      return;
    }
    let objectId: string | null = revision.id;
    let baseUpdatedAt: string | null = revision.updated_at ?? null;
    let payload: Record<string, unknown>;
    if (queueOperation === "revision.update") {
      payload = {
        prepared_by_position: String(form.get("prepared_by_position")),
      };
    } else if (queueOperation === "assignment.create") {
      objectId = crypto.randomUUID();
      baseUpdatedAt = null;
      payload = {
        position: Number(form.get("position")),
        function: String(form.get("function")),
        channel_name: String(form.get("channel_name")),
        assignment: String(form.get("assignment") || ""),
        remarks: String(form.get("remarks") || ""),
      };
    } else if (queueOperation === "assignment.update") {
      objectId = assignment?.id ?? null;
      baseUpdatedAt = assignment?.updated_at ?? null;
      payload = { remarks: String(form.get("remarks")) };
    } else {
      objectId = assignment?.id ?? null;
      baseUpdatedAt = assignment?.updated_at ?? null;
      payload = {};
    }
    setBusy(true);
    try {
      const updated = await queueOfflineMutation(vault, passphrase, {
        operation: queueOperation,
        revision_id: revisionId,
        object_id: objectId,
        payload,
        base_updated_at: baseUpdatedAt,
      });
      setVault(updated);
      formElement.reset();
      setQueueOperation("revision.update");
      setMessage(
        "Change added to the ordered encrypted queue. It has not changed the server record.",
      );
      setError("");
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Unable to queue change.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleCancel(mutation: OfflineMutation) {
    if (!vault) return;
    try {
      const updated = await cancelPendingMutation(
        vault,
        passphrase,
        mutation.id,
      );
      setVault(updated);
      setMessage(
        "Pending local change cancelled; the cancellation is retained locally.",
      );
      setError("");
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Unable to cancel change.",
      );
    }
  }

  async function handleSynchronize() {
    if (!vault || !online || vault.mutations.length === 0) return;
    setBusy(true);
    try {
      const result = await synchronizeOfflinePackage(
        vault.package.id,
        vault.mutations,
      );
      const updated = await applySynchronizationResult(
        vault,
        passphrase,
        result,
      );
      setVault(updated);
      setMessage(
        result.partial
          ? "Synchronization completed partially. Review every conflict or rejection."
          : "All pending changes synchronized in verified sequence order.",
      );
      setError("");
      await refresh();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Synchronization did not complete.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleResolution(
    mutation: OfflineMutation,
    decision: "discard" | "requeue",
  ) {
    if (!vault) return;
    setBusy(true);
    try {
      await resolveOfflineConflict(vault.package.id, {
        mutation_id: mutation.id,
        decision,
        explanation:
          decision === "discard"
            ? "Operator chose to retain the current server record."
            : "Operator will refresh the package and create a replacement change.",
      });
      const updated = await removeResolvedMutation(
        vault,
        passphrase,
        mutation.id,
      );
      setVault(updated);
      setMessage(
        decision === "discard"
          ? "Conflict resolved by retaining the server record."
          : "Conflict recorded. Create a new package from current server data, then requeue the change. No automatic merge occurred.",
      );
      setError("");
      await refresh();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Unable to record conflict decision.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleLock() {
    if (!vault) return;
    setBusy(true);
    let serverLockFailed = false;
    if (online && selectedServerPackage?.current_status === "active") {
      try {
        await lockOfflinePackage(vault.package.id);
      } catch {
        serverLockFailed = true;
      }
    }
    setVault(null);
    setPassphrase("");
    try {
      setMessage(
        serverLockFailed
          ? "Local package locked and its key was removed from this session."
          : "Package locked. Its encryption key and passphrase were removed from this session.",
      );
      await refresh();
      setError(
        serverLockFailed
          ? "The server package could not be locked. Reconnect and lock or purge it before continuing."
          : "",
      );
    } catch (caught) {
      setError(
        caught instanceof Error
          ? `The local package is locked. ${caught.message}`
          : "The local package is locked, but server status could not be refreshed.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handlePurge(packageId: string) {
    if (
      !window.confirm(
        "Purge this encrypted package from the device? Server evidence will be retained, but packaged content will be cleared.",
      )
    ) {
      return;
    }
    setBusy(true);
    let serverPurgeFailed = false;
    try {
      if (online) {
        try {
          await purgeOfflinePackage(packageId);
        } catch {
          serverPurgeFailed = true;
        }
      }
      await purgeLocalPackage(packageId);
      if (vault?.package.id === packageId) {
        setVault(null);
        setPassphrase("");
      }
      setMessage(
        serverPurgeFailed || !online
          ? "Encrypted local content purged. The server package was not purged; reconnect and complete that step if required."
          : "Encrypted local content purged; retained server evidence was not deleted.",
      );
      await refresh();
      setError(
        serverPurgeFailed
          ? "The server package could not be purged. Its protected server copy remains available under normal access controls."
          : "",
      );
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Unable to purge package.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleSupport() {
    if (!vault) return;
    try {
      const server = online
        ? await getOfflineSupportBundle(vault.package.id)
        : { unavailable_offline: true };
      downloadJson(`offline-support-${vault.package.id}.json`, {
        server,
        local: createLocalSupportBundle(vault),
      });
      setMessage(
        "Support bundle exported without tokens, keys, passphrases, ciphertext, incident content, or mutation payloads.",
      );
      setError("");
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Unable to export support bundle.",
      );
    }
  }

  async function handleClearCaches() {
    try {
      await clearOfflineRuntimeCaches();
      setMessage(
        "Runtime app-shell caches cleared. Encrypted incident packages were not touched.",
      );
      setError("");
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Unable to clear caches.",
      );
    }
  }

  const vaultRevisions =
    vault?.package.payload_snapshot.revisions?.filter(
      (revision) => revision.status === "draft",
    ) ?? [];

  return (
    <section className="offline-panel" aria-labelledby="offline-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Controlled continuity</p>
          <h2 id="offline-heading">Offline and intermittent operation</h2>
        </div>
        <span
          className={`connectivity-state ${online ? "online" : "offline"}`}
          role="status"
        >
          {online ? "Connected" : "Offline"}
        </span>
      </div>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {message && (
        <p className="status-message" role="status" aria-live="polite">
          {message}
        </p>
      )}

      {!capability ? (
        <p>Loading offline capability…</p>
      ) : (
        <div className="offline-status-grid">
          <article className="resource-card">
            <strong>
              {capability.enabled ? "Packaging enabled" : "Packaging disabled"}
            </strong>
            <span>
              Non-synthetic use:{" "}
              {capability.approved_for_non_synthetic_use
                ? "approved"
                : "not approved"}
            </span>
            <span>
              Limit: {formatBytes(capability.limits.maximum_package_bytes)} ·{" "}
              {capability.limits.maximum_queue_items} queued changes
            </span>
            <p>{capability.warning}</p>
          </article>
          <article className="resource-card">
            <strong>Local protection</strong>
            <span>{capability.protection.browser_storage}</span>
            <span>{capability.protection.key_derivation}</span>
            <span>{capability.protection.unlock_material}</span>
            <p>{capability.protection.limitation}</p>
          </article>
          <article className="resource-card">
            <strong>Conflict rule</strong>
            <p>{capability.conflict_policy}</p>
            <span>Approved revisions always remain read-only.</span>
          </article>
        </div>
      )}

      <details>
        <summary>Offline-capable and unavailable operations</summary>
        <div className="offline-capability-lists">
          <div>
            <h3>Available after explicit packaging</h3>
            <ul>
              {capability?.supported_operations.map((item) => (
                <li key={item}>{item.replace(".", " ")}</li>
              ))}
            </ul>
          </div>
          <div>
            <h3>Unavailable offline</h3>
            <ul>
              {capability?.unsupported_operations.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        </div>
      </details>

      {incident && capability?.enabled && (
        <form className="offline-builder" onSubmit={handleCreate}>
          <h3>Create an explicitly scoped encrypted package</h3>
          <fieldset>
            <legend>Plan revisions (at least one)</legend>
            {revisions.length === 0 ? (
              <p className="empty">No plan revisions are available.</p>
            ) : (
              revisions.map((revision) => (
                <label key={revision.id} className="check-row">
                  <input
                    type="checkbox"
                    checked={selectedRevisions.includes(revision.id)}
                    onChange={() =>
                      toggle(
                        revision.id,
                        selectedRevisions,
                        setSelectedRevisions,
                      )
                    }
                  />
                  {revision.planTitle} revision {revision.number} —{" "}
                  {revision.status}
                  {revision.status === "approved" ? " (read-only)" : ""}
                </label>
              ))
            )}
          </fieldset>
          <details>
            <summary>
              Select optional libraries, sites, map, and terrain
            </summary>
            <fieldset>
              <legend>Reference library releases</legend>
              {releases.map((release) => (
                <label key={release.id} className="check-row">
                  <input
                    type="checkbox"
                    checked={selectedReleases.includes(release.id)}
                    onChange={() =>
                      toggle(release.id, selectedReleases, setSelectedReleases)
                    }
                  />
                  {release.source.name} {release.version}
                </label>
              ))}
              {releases.length === 0 && (
                <p className="empty">No library releases are available.</p>
              )}
            </fieldset>
            <fieldset>
              <legend>Map sites</legend>
              {sites.map((site) => (
                <label key={site.id} className="check-row">
                  <input
                    type="checkbox"
                    checked={selectedSites.includes(site.id)}
                    onChange={() =>
                      toggle(site.id, selectedSites, setSelectedSites)
                    }
                  />
                  {site.name}
                </label>
              ))}
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={includeMap}
                  disabled={selectedSites.length === 0}
                  onChange={(event) => setIncludeMap(event.target.checked)}
                />
                Include offline vector map metadata (no third-party tiles)
              </label>
            </fieldset>
            <fieldset>
              <legend>Completed or retained terrain analyses</legend>
              {terrain.map((analysis) => (
                <label key={analysis.id} className="check-row">
                  <input
                    type="checkbox"
                    checked={selectedTerrain.includes(analysis.id)}
                    onChange={() =>
                      toggle(analysis.id, selectedTerrain, setSelectedTerrain)
                    }
                  />
                  {analysis.engine_version} · {analysis.job_state}
                </label>
              ))}
            </fieldset>
            <p className="empty">
              Attachments are unavailable because no controlled attachment
              subsystem exists in this release.
            </p>
          </details>
          <div className="compact-form">
            <label>
              Expiration
              <select
                name="expires_in_hours"
                defaultValue={capability.limits.default_expiration_hours}
              >
                {[
                  ...new Set([
                    8,
                    24,
                    48,
                    capability.limits.default_expiration_hours,
                    capability.limits.maximum_expiration_hours,
                  ]),
                ]
                  .filter(
                    (hours) =>
                      hours <= capability.limits.maximum_expiration_hours,
                  )
                  .sort((left, right) => left - right)
                  .map((hours) => (
                    <option key={hours} value={hours}>
                      {hours} hours
                      {hours === capability.limits.maximum_expiration_hours
                        ? " (maximum)"
                        : ""}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              Device-only encryption passphrase
              <input
                type="password"
                autoComplete="new-password"
                minLength={12}
                value={passphrase}
                onChange={(event) => setPassphrase(event.target.value)}
                required
              />
            </label>
            <button
              type="submit"
              disabled={
                busy ||
                !online ||
                selectedRevisions.length === 0 ||
                passphrase.length < 12
              }
            >
              Encrypt package on this device
            </button>
          </div>
        </form>
      )}

      <div className="offline-package-grid">
        <section aria-labelledby="device-packages-heading">
          <h3 id="device-packages-heading">
            Encrypted packages on this device
          </h3>
          {localPackages.length === 0 ? (
            <p className="empty">No encrypted packages are stored locally.</p>
          ) : (
            localPackages.map((item) => {
              const server = packages.find(
                (candidate) => candidate.id === item.id,
              );
              return (
                <article className="resource-card" key={item.id}>
                  <strong>{item.id}</strong>
                  <span>
                    {server?.current_status ?? item.status} · expires{" "}
                    {new Date(item.expires_at).toLocaleString()}
                  </span>
                  <span>Manifest {item.manifest_sha256.slice(0, 12)}…</span>
                  <button
                    type="button"
                    className="danger-button"
                    onClick={() => void handlePurge(item.id)}
                    disabled={busy}
                  >
                    Purge local package
                  </button>
                </article>
              );
            })
          )}
        </section>
        <form className="compact-form" onSubmit={handleUnlock}>
          <h3>Unlock a device package</h3>
          <label>
            Package
            <select name="package_id" required>
              <option value="">Select encrypted package</option>
              {localPackages.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.id} (
                  {packages.find((value) => value.id === item.id)
                    ?.current_status ?? item.status}
                  )
                </option>
              ))}
            </select>
          </label>
          <label>
            Passphrase
            <input
              type="password"
              autoComplete="current-password"
              minLength={12}
              value={passphrase}
              onChange={(event) => setPassphrase(event.target.value)}
              required
            />
          </label>
          <button type="submit" disabled={busy || passphrase.length < 12}>
            Unlock for this session
          </button>
        </form>
      </div>

      {vault && (
        <section
          className="offline-vault"
          aria-labelledby="offline-vault-heading"
        >
          <h3 id="offline-vault-heading">Unlocked package review</h3>
          <p>
            Package {vault.package.id} · {vault.mutations.length} pending or
            unresolved change{vault.mutations.length === 1 ? "" : "s"}
          </p>
          {selectedServerPackage?.current_status === "revoked" && (
            <p className="error" role="alert">
              Incident access was revoked. Synchronization and unlock are
              blocked; lock or purge the local package.
            </p>
          )}
          <form className="compact-form" onSubmit={handleQueue}>
            <h4>Queue a bounded draft change</h4>
            <label>
              Offline operation
              <select
                name="offline_operation"
                value={queueOperation}
                onChange={(event) =>
                  setQueueOperation(
                    event.target.value as OfflineMutation["operation"],
                  )
                }
              >
                <option value="revision.update">
                  Update revision prepared-by position
                </option>
                <option value="assignment.create">Create assignment row</option>
                <option value="assignment.update">
                  Update assignment remarks
                </option>
                <option value="assignment.delete">Delete assignment row</option>
              </select>
            </label>
            <label>
              Draft revision
              <select name="revision_id" required>
                <option value="">Select revision</option>
                {vaultRevisions.map((revision) => (
                  <option key={revision.id} value={revision.id}>
                    Revision {revision.number}
                  </option>
                ))}
              </select>
            </label>
            {(queueOperation === "assignment.update" ||
              queueOperation === "assignment.delete") && (
              <label>
                Assignment
                <select name="assignment_id" required>
                  <option value="">Select assignment</option>
                  {vaultRevisions.flatMap((revision) =>
                    revision.assignments.map((assignment: PlanAssignment) => (
                      <option key={assignment.id} value={assignment.id}>
                        Row {assignment.position}: {assignment.channel_name}
                      </option>
                    )),
                  )}
                </select>
              </label>
            )}
            {queueOperation === "revision.update" && (
              <label>
                Prepared-by position
                <input name="prepared_by_position" required maxLength={160} />
              </label>
            )}
            {queueOperation === "assignment.create" && (
              <>
                <label>
                  Row position
                  <input name="position" type="number" min="1" required />
                </label>
                <label>
                  Function
                  <input name="function" required maxLength={160} />
                </label>
                <label>
                  Channel name
                  <input name="channel_name" required maxLength={160} />
                </label>
                <label>
                  Assignment
                  <input name="assignment" maxLength={200} />
                </label>
                <label>
                  Remarks
                  <input name="remarks" maxLength={500} />
                </label>
              </>
            )}
            {queueOperation === "assignment.update" && (
              <label>
                New remarks
                <input name="remarks" required maxLength={500} />
              </label>
            )}
            {queueOperation === "assignment.delete" && (
              <p className="warning">
                Deletion is queued for explicit review; the server record is
                unchanged until synchronization succeeds.
              </p>
            )}
            <button type="submit" disabled={busy}>
              Add to encrypted queue
            </button>
          </form>

          <div aria-live="polite">
            {vault.mutations.length === 0 ? (
              <p className="empty">No pending changes.</p>
            ) : (
              <ol className="offline-queue">
                {vault.mutations.map((mutation, index) => (
                  <li key={mutation.id}>
                    <strong>{mutationSummary(mutation)}</strong>
                    <span>Digest {mutation.mutation_sha256.slice(0, 12)}…</span>
                    {typeof mutation.sync_result?.detail === "string" && (
                      <p>{mutation.sync_result.detail}</p>
                    )}
                    {!mutation.sync_status && (
                      <button
                        type="button"
                        onClick={() => void handleCancel(mutation)}
                        disabled={busy || index !== vault.mutations.length - 1}
                      >
                        Cancel pending change
                      </button>
                    )}
                    {mutation.sync_status === "conflict" && (
                      <div className="button-row">
                        <button
                          type="button"
                          onClick={() =>
                            void handleResolution(mutation, "discard")
                          }
                          disabled={busy}
                        >
                          Keep server record
                        </button>
                        <button
                          type="button"
                          onClick={() =>
                            void handleResolution(mutation, "requeue")
                          }
                          disabled={busy}
                        >
                          Refresh and requeue
                        </button>
                      </div>
                    )}
                  </li>
                ))}
              </ol>
            )}
          </div>

          <div className="button-row">
            <button
              type="button"
              onClick={() => void handleSynchronize()}
              disabled={
                busy ||
                !online ||
                vault.mutations.length === 0 ||
                selectedServerPackage?.current_status !== "active"
              }
            >
              Review complete — synchronize
            </button>
            <button
              type="button"
              onClick={() => void handleLock()}
              disabled={busy}
            >
              Lock package
            </button>
            <button
              type="button"
              onClick={() => void handleSupport()}
              disabled={busy}
            >
              Export support bundle
            </button>
          </div>
        </section>
      )}

      <section
        className="offline-maintenance"
        aria-labelledby="offline-maintenance-heading"
      >
        <h3 id="offline-maintenance-heading">
          App shell and recovery controls
        </h3>
        <div className="button-row">
          <button type="button" onClick={() => void checkForOfflineUpdate()}>
            Check for app update
          </button>
          {updateReady && (
            <button type="button" onClick={() => void activateOfflineUpdate()}>
              Activate downloaded update
            </button>
          )}
          <button type="button" onClick={() => void handleClearCaches()}>
            Clear runtime caches
          </button>
        </div>
        <p>
          Clearing runtime caches does not delete encrypted incident packages.
          Package purge is a separate, explicit action.
        </p>
      </section>
    </section>
  );
}
