import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  checkoutInventoryAsset,
  createInventoryAsset,
  createProgrammingRecord,
  listAssetCheckouts,
  listInventoryAssets,
  listProgrammingRecords,
  resolveInventoryHold,
  returnInventoryAsset,
} from "./api";
import type {
  AssetCheckout,
  CurrentUser,
  Incident,
  InventoryAsset,
  ProgrammingRecord,
} from "./types";

const jurisdictions = [
  "AL",
  "AK",
  "AZ",
  "AR",
  "CA",
  "CO",
  "CT",
  "DE",
  "DC",
  "FL",
  "GA",
  "HI",
  "ID",
  "IL",
  "IN",
  "IA",
  "KS",
  "KY",
  "LA",
  "ME",
  "MD",
  "MA",
  "MI",
  "MN",
  "MS",
  "MO",
  "MT",
  "NE",
  "NV",
  "NH",
  "NJ",
  "NM",
  "NY",
  "NC",
  "ND",
  "OH",
  "OK",
  "OR",
  "PA",
  "RI",
  "SC",
  "SD",
  "TN",
  "TX",
  "UT",
  "VT",
  "VA",
  "WA",
  "WV",
  "WI",
  "WY",
];

interface Props {
  incident: Incident | null;
  currentUser: CurrentUser;
}

export function AssetManagementWorkspace({ incident, currentUser }: Props) {
  const [assets, setAssets] = useState<InventoryAsset[]>([]);
  const [checkouts, setCheckouts] = useState<AssetCheckout[]>([]);
  const [programming, setProgramming] = useState<ProgrammingRecord[]>([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [returningCheckout, setReturningCheckout] =
    useState<AssetCheckout | null>(null);
  const [returnCondition, setReturnCondition] = useState("normal");
  const canManage = currentUser.permissions.includes("inventory.manage");

  const refresh = useCallback(async () => {
    setError("");
    try {
      const [assetItems, programmingItems, checkoutItems] = await Promise.all([
        listInventoryAssets(),
        listProgrammingRecords(),
        incident ? listAssetCheckouts(incident.id) : Promise.resolve([]),
      ]);
      setAssets(assetItems);
      setProgramming(programmingItems);
      setCheckouts(checkoutItems);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Unable to load asset inventory.",
      );
    }
  }, [incident]);

  useEffect(() => void refresh(), [refresh]);

  const availableRadios = useMemo(
    () =>
      assets.filter(
        (asset) =>
          asset.category === "radio" &&
          ["in_service", "spare"].includes(asset.status),
      ),
    [assets],
  );

  async function submit(
    form: HTMLFormElement,
    operation: () => Promise<unknown>,
    success: string,
  ) {
    setError("");
    setMessage("");
    try {
      await operation();
      form.reset();
      setMessage(success);
      await refresh();
      return true;
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "The inventory action failed.",
      );
      return false;
    }
  }

  function handleAsset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    void submit(
      form,
      () =>
        createInventoryAsset({
          asset_id: data.get("asset_id"),
          category: data.get("category"),
          parent: data.get("parent") || null,
          manufacturer: data.get("manufacturer"),
          model: data.get("model"),
          serial_number: data.get("serial_number"),
          alias: data.get("alias"),
          notes: data.get("notes"),
        }),
      "Asset added.",
    );
  }

  function handleCheckout(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!incident) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    void submit(
      form,
      () =>
        checkoutInventoryAsset({
          incident: incident.id,
          asset: data.get("asset"),
          assigned_name: data.get("assigned_name"),
          assigned_organization: data.get("assigned_organization"),
          driver_license_jurisdiction: data.get("jurisdiction"),
          driver_license_number: data.get("driver_license_number"),
        }),
      "Radio checked out.",
    );
  }

  function handleProgramming(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    void submit(
      form,
      () =>
        createProgrammingRecord({
          asset: data.get("asset"),
          template_name: data.get("template_name"),
          template_version: data.get("template_version"),
          programmed_at: data.get("programmed_at"),
          codeplug_backup_saved: data.get("codeplug_backup_saved") === "on",
          backup_note: data.get("backup_note"),
        }),
      "Programming record saved.",
    );
  }

  function handleReturn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!returningCheckout) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    const condition = String(data.get("condition"));
    void submit(
      form,
      () =>
        returnInventoryAsset(returningCheckout.id, {
          condition,
          hold_reason: String(data.get("hold_reason") ?? ""),
        }),
      condition === "normal"
        ? "Radio returned; driver's-license number deleted."
        : "Accountability hold recorded; driver's-license number retained.",
    ).then((succeeded) => {
      if (succeeded) setReturningCheckout(null);
    });
  }

  function handleHoldResolution(
    event: FormEvent<HTMLFormElement>,
    checkout: AssetCheckout,
  ) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    void submit(
      form,
      () =>
        resolveInventoryHold(checkout.id, {
          asset_status: String(data.get("asset_status")),
          resolution_note: String(data.get("resolution_note")),
        }),
      "Accountability hold resolved; driver's-license number deleted.",
    );
  }

  function printAssetLabels() {
    const cleanup = () => document.body.classList.remove("asset-label-print");
    document.body.classList.add("asset-label-print");
    window.addEventListener("afterprint", cleanup, { once: true });
    window.print();
  }

  return (
    <section
      className="planning-panel"
      aria-labelledby="asset-management-heading"
    >
      <div className="section-heading">
        <div>
          <p className="eyebrow">Accountable property</p>
          <h2 id="asset-management-heading">Asset Management</h2>
        </div>
        <span className="count">{assets.length}</span>
      </div>
      <p>
        Track communication assets, accountable radio checkout, parent and child
        equipment, and codeplug-backup attestations.
      </p>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {message && <p role="status">{message}</p>}
      {assets.length > 0 && (
        <button
          type="button"
          className="secondary-button"
          onClick={printAssetLabels}
        >
          Print parent and child asset labels
        </button>
      )}
      {!incident && (
        <p className="empty">
          Select an incident to view or perform accountable radio checkout.
        </p>
      )}
      {canManage && (
        <div className="workspace-grid">
          <form className="compact-form" onSubmit={handleAsset}>
            <h3>Add asset</h3>
            <label>
              Asset ID
              <input name="asset_id" required />
            </label>
            <label>
              Category
              <select name="category" required>
                <option value="radio">Radio</option>
                <option value="battery">Battery</option>
                <option value="antenna">Antenna</option>
                <option value="cable">Programming cable</option>
                <option value="microphone">Microphone</option>
                <option value="accessory">Other accessory</option>
              </select>
            </label>
            <label>
              Parent asset
              <select name="parent">
                <option value="">None</option>
                {assets.map((asset) => (
                  <option key={asset.id} value={asset.id}>
                    {asset.asset_id}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Manufacturer
              <input name="manufacturer" />
            </label>
            <label>
              Model
              <input name="model" />
            </label>
            <label>
              Serial number
              <input name="serial_number" />
            </label>
            <label>
              Alias
              <input name="alias" />
            </label>
            <label>
              Notes
              <textarea name="notes" rows={2} />
            </label>
            <button type="submit">Add asset</button>
          </form>
          {incident && (
            <form className="compact-form" onSubmit={handleCheckout}>
              <h3>Check out radio</h3>
              <label>
                Radio
                <select name="asset" required>
                  <option value="">Select radio</option>
                  {availableRadios.map((asset) => (
                    <option key={asset.id} value={asset.id}>
                      {asset.asset_id} {asset.alias && `— ${asset.alias}`}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Assigned individual
                <input name="assigned_name" required />
              </label>
              <label>
                Agency or organization
                <input name="assigned_organization" required />
              </label>
              <label>
                Driver's-license issuing state
                <select name="jurisdiction" required>
                  <option value="">Select state</option>
                  {jurisdictions.map((state) => (
                    <option key={state}>{state}</option>
                  ))}
                </select>
              </label>
              <label>
                Driver's-license number
                <input
                  name="driver_license_number"
                  autoComplete="off"
                  required
                  minLength={4}
                  maxLength={32}
                />
              </label>
              <button type="submit">Check out radio</button>
            </form>
          )}
          <form className="compact-form" onSubmit={handleProgramming}>
            <h3>Record programming</h3>
            <label>
              Radio
              <select name="asset" required>
                <option value="">Select radio</option>
                {assets
                  .filter((asset) => asset.category === "radio")
                  .map((asset) => (
                    <option key={asset.id} value={asset.id}>
                      {asset.asset_id}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              Template name
              <input name="template_name" required />
            </label>
            <label>
              Template version
              <input name="template_version" />
            </label>
            <label>
              Programmed at
              <input name="programmed_at" type="datetime-local" required />
            </label>
            <label className="checkbox-label">
              <input name="codeplug_backup_saved" type="checkbox" required />{" "}
              Codeplug backup saved
            </label>
            <label>
              Backup procedure note
              <input name="backup_note" maxLength={300} />
            </label>
            <button type="submit">Save programming record</button>
          </form>
        </div>
      )}
      {returningCheckout && (
        <form
          className="compact-form"
          onSubmit={handleReturn}
          aria-labelledby="record-return-heading"
        >
          <h3 id="record-return-heading">
            Record return for {returningCheckout.asset_detail.asset_id}
          </h3>
          <label>
            Condition
            <select
              name="condition"
              value={returnCondition}
              onChange={(event) => setReturnCondition(event.target.value)}
            >
              <option value="normal">Returned without damage</option>
              <option value="damaged">Damaged</option>
              <option value="lost">Lost or not returned</option>
              <option value="disputed">Disputed</option>
            </select>
          </label>
          {returnCondition !== "normal" && (
            <label>
              Incident report or accountability-hold reason
              <textarea name="hold_reason" rows={3} required maxLength={2000} />
            </label>
          )}
          <p>
            {returnCondition === "normal"
              ? "Saving this return permanently deletes the driver's-license number."
              : "The driver's-license number remains encrypted until the hold is resolved."}
          </p>
          <div className="button-row">
            <button type="submit">Save return</button>
            <button
              className="secondary-button"
              type="button"
              onClick={() => setReturningCheckout(null)}
            >
              Cancel
            </button>
          </div>
        </form>
      )}
      <h3>Assets</h3>
      <div className="resource-grid">
        {assets.map((asset) => (
          <article className="resource-card" key={asset.id}>
            <strong>{asset.asset_id}</strong>
            <span>
              {asset.category.replace("_", " ")} ·{" "}
              {asset.status.replace("_", " ")}
            </span>
            <span>
              {[asset.manufacturer, asset.model, asset.alias]
                .filter(Boolean)
                .join(" · ") || "No description"}
            </span>
            <small>
              Serial: {asset.serial_number || "Not recorded"}
              {asset.parent ? " · Child asset" : ""}
            </small>
          </article>
        ))}
      </div>
      {incident && (
        <>
          <h3>Incident checkouts</h3>
          <div className="resource-grid">
            {checkouts.map((checkout) => (
              <article className="resource-card" key={checkout.id}>
                <strong>
                  {checkout.asset_detail.asset_id} — {checkout.assigned_name}
                </strong>
                <span>
                  {checkout.assigned_organization} · {checkout.state}
                </span>
                <span>
                  DL: {checkout.driver_license_jurisdiction}{" "}
                  {checkout.driver_license_number ?? "Deleted after return"}
                </span>
                {checkout.hold_reason && (
                  <p>
                    <strong>Hold:</strong> {checkout.hold_reason}
                  </p>
                )}
                {checkout.hold_resolution_note && (
                  <p>
                    <strong>Resolution:</strong> {checkout.hold_resolution_note}
                  </p>
                )}
                {canManage && checkout.state === "active" && (
                  <button
                    type="button"
                    onClick={() => {
                      setReturnCondition("normal");
                      setReturningCheckout(checkout);
                    }}
                  >
                    Record return or exception
                  </button>
                )}
                {canManage && checkout.state === "hold" && (
                  <form
                    className="compact-form"
                    onSubmit={(event) => handleHoldResolution(event, checkout)}
                  >
                    <h4>Resolve accountability hold</h4>
                    <label>
                      Final asset status
                      <select name="asset_status" required>
                        <option value="in_service">In service</option>
                        <option value="maintenance">Maintenance</option>
                        <option value="retired">Retired</option>
                      </select>
                    </label>
                    <label>
                      Resolution note
                      <textarea
                        name="resolution_note"
                        required
                        rows={2}
                        maxLength={2000}
                      />
                    </label>
                    <button type="submit">Resolve hold and delete DL</button>
                  </form>
                )}
              </article>
            ))}
          </div>
        </>
      )}
      <h3>Programming history</h3>
      <div className="resource-grid">
        {programming.map((record) => (
          <article className="resource-card" key={record.id}>
            <strong>
              {assets.find((asset) => asset.id === record.asset)?.asset_id ??
                "Asset"}{" "}
              — {record.template_name}
            </strong>
            <span>
              {record.template_version || "No version"} ·{" "}
              {new Date(record.programmed_at).toLocaleString()}
            </span>
            <span>
              Codeplug backup saved:{" "}
              {record.codeplug_backup_saved ? "Yes" : "No"}
            </span>
            <small>
              Confirmed by {record.confirmed_by_username} at{" "}
              {new Date(record.confirmed_at).toLocaleString()}
            </small>
          </article>
        ))}
      </div>
      <section className="asset-label-sheet" aria-hidden="true">
        {assets.map((asset) => {
          const parent = assets.find(
            (candidate) => candidate.id === asset.parent,
          );
          const childCount = assets.filter(
            (candidate) => candidate.parent === asset.id,
          ).length;
          return (
            <article className="asset-print-label" key={`label-${asset.id}`}>
              <strong>{asset.asset_id}</strong>
              <span>{asset.category.replace("_", " ")}</span>
              <span>
                {parent
                  ? `CHILD OF ${parent.asset_id}`
                  : childCount > 0
                    ? `PARENT ASSET · ${childCount} CHILD${childCount === 1 ? "" : "REN"}`
                    : "STANDALONE ASSET"}
              </span>
              <small>
                {[asset.manufacturer, asset.model, asset.serial_number]
                  .filter(Boolean)
                  .join(" · ")}
              </small>
            </article>
          );
        })}
      </section>
    </section>
  );
}
