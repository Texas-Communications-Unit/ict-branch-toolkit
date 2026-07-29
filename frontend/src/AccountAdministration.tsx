import { FormEvent, useCallback, useEffect, useState } from "react";

import {
  createLocalContingencyAccount,
  listLocalContingencyAccounts,
  setLocalContingencyAccountStatus,
  signOutLocalContingencyAccount,
} from "./api";
import type {
  CurrentUser,
  Incident,
  LocalContingencyAccount,
  ToolkitRole,
} from "./types";

const ROLES: { value: ToolkitRole; label: string }[] = [
  { value: "administrator", label: "Administrator" },
  { value: "coml", label: "COML" },
  { value: "comc", label: "COMC" },
  { value: "comt", label: "COMT" },
  { value: "auxcomm", label: "AUXCOMM" },
  { value: "incm", label: "INCM" },
  { value: "contributor", label: "Contributor" },
  { value: "read_only", label: "Read-only" },
];

export function AccountAdministration({
  currentUser,
  incidents,
}: {
  currentUser: CurrentUser | null;
  incidents: Incident[];
}) {
  const [accounts, setAccounts] = useState<LocalContingencyAccount[]>([]);
  const [issued, setIssued] = useState<LocalContingencyAccount | null>(null);
  const [message, setMessage] = useState("");
  const authorized =
    currentUser?.permissions.includes("account.manage") ?? false;

  const refresh = useCallback(async () => {
    if (!authorized) return;
    setAccounts(await listLocalContingencyAccounts());
  }, [authorized]);

  useEffect(() => {
    void refresh().catch((error) =>
      setMessage(
        error instanceof Error ? error.message : "Account load failed.",
      ),
    );
  }, [refresh]);

  if (!authorized) return null;

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    try {
      const account = await createLocalContingencyAccount({
        username: String(data.get("username")),
        display_name: String(data.get("displayName")),
        role: String(data.get("role")) as ToolkitRole,
        reason: String(data.get("reason")),
        incidents: data.getAll("incidents").map(String),
      });
      setIssued(account);
      setMessage("");
      form.reset();
      await refresh();
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Account creation failed.",
      );
    }
  }

  async function changeStatus(
    account: LocalContingencyAccount,
    action: "enable" | "disable",
  ) {
    const reason = window.prompt(
      `Record why ${account.username} is being ${action}d:`,
    );
    if (!reason?.trim()) return;
    try {
      await setLocalContingencyAccountStatus(account.username, action, reason);
      await refresh();
      setMessage("");
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Account update failed.",
      );
    }
  }

  return (
    <section
      className="planning-panel account-administration"
      aria-labelledby="local-accounts-heading"
    >
      <div className="section-heading">
        <div>
          <p className="eyebrow">Continuity access</p>
          <h2 id="local-accounts-heading">Local contingency accounts</h2>
        </div>
        <span className="count">{accounts.length}</span>
      </div>
      <p>
        Create individually attributable local access only when CiviCRM access
        is unavailable or an operational exception is documented. Shared
        accounts are prohibited.
      </p>
      {message && (
        <p role="alert" className="error">
          {message}
        </p>
      )}
      {issued?.temporary_password && (
        <div className="credential-result" role="status">
          <strong>Copy this one-time temporary credential now.</strong>
          <span>
            Username: <code>{issued.username}</code>
          </span>
          <span>
            Temporary password: <code>{issued.temporary_password}</code>
          </span>
          <small>
            It is returned only in this response. The user must replace it
            before sign-in.
          </small>
          <button type="button" onClick={() => setIssued(null)}>
            I stored it securely
          </button>
        </div>
      )}
      <form className="compact-form" onSubmit={(event) => void create(event)}>
        <label>
          Username
          <input name="username" autoComplete="off" required />
        </label>
        <label>
          Display name
          <input name="displayName" required />
        </label>
        <label>
          Global/default role
          <select name="role" defaultValue="read_only" required>
            {ROLES.map((role) => (
              <option key={role.value} value={role.value}>
                {role.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Incident memberships
          <select
            name="incidents"
            multiple
            size={Math.max(2, Math.min(5, incidents.length))}
          >
            {incidents.map((incident) => (
              <option key={incident.id} value={incident.id}>
                {incident.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Operational reason
          <textarea name="reason" maxLength={500} required />
        </label>
        <button type="submit">Create local contingency account</button>
      </form>
      <div className="incident-list">
        {accounts.map((account) => (
          <article className="resource-card" key={account.username}>
            <strong>
              {account.display_name} ({account.username})
            </strong>
            <span>
              {account.role} · {account.is_active ? "Active" : "Disabled"}
              {account.must_change_password ? " · Activation pending" : ""}
            </span>
            <small>{account.reason}</small>
            <div className="button-row">
              <button
                type="button"
                onClick={() =>
                  void changeStatus(
                    account,
                    account.is_active ? "disable" : "enable",
                  )
                }
              >
                {account.is_active ? "Disable account" : "Enable account"}
              </button>
              <button
                type="button"
                className="secondary-button"
                onClick={() => {
                  if (
                    !window.confirm(
                      `Sign out every active session for ${account.username}?`,
                    )
                  )
                    return;
                  void signOutLocalContingencyAccount(account.username)
                    .then(refresh)
                    .catch((error) =>
                      setMessage(
                        error instanceof Error
                          ? error.message
                          : "Session revocation failed.",
                      ),
                    );
                }}
              >
                Sign out all sessions
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
