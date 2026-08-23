import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  checkoutInventoryAsset,
  createChargingRecord,
  createInventoryAsset,
  createMaintenanceRecord,
  createProgrammingRecord,
  listAssetCheckouts,
  listChargingRecords,
  listInventoryAssets,
  listMaintenanceRecords,
  listProgrammingRecords,
  resolveInventoryHold,
  returnInventoryAsset,
  updateInventoryAsset,
} from "./api";
import type {
  AssetCheckout,
  ChargingRecord,
  CurrentUser,
  Incident,
  InventoryAsset,
  MaintenanceRecord,
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
  const [maintenance, setMaintenance] = useState<MaintenanceRecord[]>([]);
  const [charging, setCharging] = useState<ChargingRecord[]>([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [returningCheckout, setReturningCheckout] =
    useState<AssetCheckout | null>(null);
  const [returnCondition, setReturnCondition] = useState("normal");
  const [assetSearch, setAssetSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [assetOrdering, setAssetOrdering] = useState("asset_id");
  const [editingAsset, setEditingAsset] = useState<InventoryAsset | null>(null);
  const canManage = currentUser.permissions.includes("inventory.manage");

  const refresh = useCallback(async () => {
    setError("");
    try {
      const [
        assetItems,
        programmingItems,
        maintenanceItems,
        chargingItems,
        checkoutItems,
      ] = await Promise.all([
        listInventoryAssets(),
        listProgrammingRecords(),
        listMaintenanceRecords(),
        listChargingRecords(),
        incident ? listAssetCheckouts(incident.id) : Promise.resolve([]),
      ]);
      setAssets(assetItems);
      setProgramming(programmingItems);
      setMaintenance(maintenanceItems);
      setCharging(chargingItems);
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

  const availableAssets = useMemo(
    () =>
      assets.filter((asset) => ["in_service", "spare"].includes(asset.status)),
    [assets],
  );
  const visibleAssets = useMemo(() => {
    const needle = assetSearch.trim().toLowerCase();
    return [...assets]
      .filter((asset) => !categoryFilter || asset.category === categoryFilter)
      .filter((asset) => !statusFilter || asset.status === statusFilter)
      .filter(
        (asset) =>
          !needle ||
          [
            asset.asset_id,
            asset.serial_number,
            asset.alias,
            asset.manufacturer,
            asset.model,
          ].some((value) => value.toLowerCase().includes(needle)),
      )
      .sort((left, right) =>
        String(left[assetOrdering as keyof InventoryAsset] ?? "").localeCompare(
          String(right[assetOrdering as keyof InventoryAsset] ?? ""),
        ),
      );
  }, [assetOrdering, assetSearch, assets, categoryFilter, statusFilter]);

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
          asset_subtype: data.get("asset_subtype"),
          flash_code: data.get("flash_code"),
          subscriber_id: data.get("subscriber_id"),
          system_ids: data.get("system_ids"),
          acquisition_date: data.get("acquisition_date") || null,
          notes: data.get("notes"),
        }),
      "Asset added.",
    );
  }

  function handleAssetUpdate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editingAsset) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    void submit(
      form,
      () =>
        updateInventoryAsset(editingAsset.id, {
          parent: data.get("parent") || null,
          manufacturer: data.get("manufacturer"),
          model: data.get("model"),
          serial_number: data.get("serial_number"),
          alias: data.get("alias"),
          asset_subtype: data.get("asset_subtype"),
          flash_code: data.get("flash_code"),
          subscriber_id: data.get("subscriber_id"),
          system_ids: data.get("system_ids"),
          acquisition_date: data.get("acquisition_date") || null,
          status: data.get("status"),
          notes: data.get("notes"),
        }),
      "Asset updated.",
    ).then((succeeded) => {
      if (succeeded) setEditingAsset(null);
    });
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
          assets: data.getAll("assets"),
          assigned_name: data.get("assigned_name"),
          assigned_organization: data.get("assigned_organization"),
          point_of_contact: data.get("point_of_contact"),
          phone_number: data.get("phone_number"),
          mailing_address: data.get("mailing_address"),
          assignment_notes: data.get("assignment_notes"),
          driver_license_jurisdiction: data.get("jurisdiction"),
          driver_license_number: data.get("driver_license_number"),
        }),
      "Assets checked out.",
    );
  }

  function handleMaintenance(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    void submit(
      form,
      () =>
        createMaintenanceRecord({
          asset: data.get("asset"),
          kind: data.get("kind"),
          performed_at: data.get("performed_at"),
          technician: data.get("technician"),
          notes: data.get("notes"),
          return_to_service: data.get("return_to_service") === "on",
        }),
      "Maintenance record saved.",
    );
  }

  function handleCharging(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    void submit(
      form,
      () =>
        createChargingRecord({
          asset: data.get("asset"),
          started_at: data.get("started_at"),
          completed_at: data.get("completed_at") || null,
          notes: data.get("notes"),
        }),
      "Charging record saved.",
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
        ? "Asset returned; driver's-license number deleted."
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
          Select an incident to view or perform accountable asset checkout.
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
              Subtype
              <input
                name="asset_subtype"
                placeholder="Handheld, mobile, base, battery type"
              />
            </label>
            <label>
              Flash code
              <input name="flash_code" />
            </label>
            <label>
              Subscriber ID
              <input name="subscriber_id" />
            </label>
            <label>
              System IDs
              <input name="system_ids" />
            </label>
            <label>
              Acquisition date
              <input name="acquisition_date" type="date" />
            </label>
            <label>
              Notes
              <textarea name="notes" rows={2} />
            </label>
            <button type="submit">Add asset</button>
          </form>
          {incident && (
            <form className="compact-form" onSubmit={handleCheckout}>
              <h3>Check out assets</h3>
              <label>
                Assets (select one or more)
                <select
                  name="assets"
                  required
                  multiple
                  size={Math.min(8, Math.max(3, availableAssets.length))}
                >
                  {availableAssets.map((asset) => (
                    <option key={asset.id} value={asset.id}>
                      {asset.asset_id} · {asset.category}{" "}
                      {asset.alias && `— ${asset.alias}`}
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
                24-hour point of contact
                <input name="point_of_contact" />
              </label>
              <label>
                Cell phone number
                <input name="phone_number" type="tel" />
              </label>
              <label>
                Mailing address
                <textarea name="mailing_address" rows={2} />
              </label>
              <label>
                Assignment notes
                <textarea name="assignment_notes" rows={2} />
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
              <button type="submit">Check out selected assets</button>
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
          <form className="compact-form" onSubmit={handleMaintenance}>
            <h3>Record maintenance</h3>
            <label>
              Asset
              <select name="asset" required>
                <option value="">Select asset</option>
                {assets.map((asset) => (
                  <option key={asset.id} value={asset.id}>
                    {asset.asset_id}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Type
              <select name="kind" required>
                <option value="inspection">Inspection</option>
                <option value="calibration">Calibration</option>
                <option value="repair">Repair</option>
                <option value="preventive">Preventive maintenance</option>
              </select>
            </label>
            <label>
              Performed at
              <input name="performed_at" type="datetime-local" required />
            </label>
            <label>
              Technician
              <input name="technician" required />
            </label>
            <label>
              Work performed
              <textarea name="notes" rows={3} required />
            </label>
            <label className="checkbox-label">
              <input name="return_to_service" type="checkbox" /> Return asset to
              service
            </label>
            <button type="submit">Save maintenance record</button>
          </form>
          <form className="compact-form" onSubmit={handleCharging}>
            <h3>Record charging</h3>
            <label>
              Battery or asset
              <select name="asset" required>
                <option value="">Select asset</option>
                {assets
                  .filter((asset) =>
                    ["battery", "radio"].includes(asset.category),
                  )
                  .map((asset) => (
                    <option key={asset.id} value={asset.id}>
                      {asset.asset_id}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              Charging started
              <input name="started_at" type="datetime-local" required />
            </label>
            <label>
              Charging completed
              <input name="completed_at" type="datetime-local" />
            </label>
            <label>
              Notes
              <input name="notes" maxLength={500} />
            </label>
            <button type="submit">Save charging record</button>
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
      {canManage && editingAsset && (
        <form className="compact-form" onSubmit={handleAssetUpdate}>
          <h4>Edit {editingAsset.asset_id}</h4>
          <label>
            Parent asset
            <select name="parent" defaultValue={editingAsset.parent ?? ""}>
              <option value="">None</option>
              {assets
                .filter((asset) => asset.id !== editingAsset.id)
                .map((asset) => (
                  <option key={asset.id} value={asset.id}>
                    {asset.asset_id}
                  </option>
                ))}
            </select>
          </label>
          <label>
            Manufacturer
            <input
              name="manufacturer"
              defaultValue={editingAsset.manufacturer}
            />
          </label>
          <label>
            Model
            <input name="model" defaultValue={editingAsset.model} />
          </label>
          <label>
            Serial number
            <input
              name="serial_number"
              defaultValue={editingAsset.serial_number}
            />
          </label>
          <label>
            Alias
            <input name="alias" defaultValue={editingAsset.alias} />
          </label>
          <label>
            Subtype
            <input
              name="asset_subtype"
              defaultValue={editingAsset.asset_subtype}
            />
          </label>
          <label>
            Flash code
            <input name="flash_code" defaultValue={editingAsset.flash_code} />
          </label>
          <label>
            Subscriber ID
            <input
              name="subscriber_id"
              defaultValue={editingAsset.subscriber_id}
            />
          </label>
          <label>
            System IDs
            <input name="system_ids" defaultValue={editingAsset.system_ids} />
          </label>
          <label>
            Acquisition date
            <input
              name="acquisition_date"
              type="date"
              defaultValue={editingAsset.acquisition_date ?? ""}
            />
          </label>
          <label>
            Status
            <select
              name="status"
              defaultValue={editingAsset.status}
              disabled={editingAsset.status === "checked_out"}
            >
              <option value="in_service">In service</option>
              <option value="spare">Spare</option>
              <option value="checked_out">Checked out</option>
              <option value="maintenance">Maintenance</option>
              <option value="retired">Retired</option>
            </select>
          </label>
          {editingAsset.status === "checked_out" && (
            <input name="status" type="hidden" value="checked_out" />
          )}
          <label>
            Notes
            <textarea name="notes" rows={3} defaultValue={editingAsset.notes} />
          </label>
          <div className="button-row">
            <button type="submit">Save asset</button>
            <button
              type="button"
              className="secondary-button"
              onClick={() => setEditingAsset(null)}
            >
              Cancel
            </button>
          </div>
        </form>
      )}
      <div className="filter-row" aria-label="Filter and sort assets">
        <label>
          Search assets
          <input
            value={assetSearch}
            onChange={(event) => setAssetSearch(event.target.value)}
            placeholder="Asset ID, serial, alias, make, or model"
          />
        </label>
        <label>
          Category
          <select
            value={categoryFilter}
            onChange={(event) => setCategoryFilter(event.target.value)}
          >
            <option value="">All categories</option>
            <option value="radio">Radio</option>
            <option value="battery">Battery</option>
            <option value="antenna">Antenna</option>
            <option value="cable">Programming cable</option>
            <option value="microphone">Microphone</option>
            <option value="accessory">Other accessory</option>
          </select>
        </label>
        <label>
          Status
          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            <option value="">All statuses</option>
            <option value="in_service">In service</option>
            <option value="spare">Spare</option>
            <option value="checked_out">Checked out</option>
            <option value="maintenance">Maintenance</option>
            <option value="retired">Retired</option>
          </select>
        </label>
        <label>
          Sort by
          <select
            value={assetOrdering}
            onChange={(event) => setAssetOrdering(event.target.value)}
          >
            <option value="asset_id">Asset ID</option>
            <option value="category">Category</option>
            <option value="status">Status</option>
            <option value="manufacturer">Manufacturer</option>
            <option value="model">Model</option>
          </select>
        </label>
      </div>
      <div className="resource-grid">
        {visibleAssets.map((asset) => (
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
            {canManage && (
              <button
                type="button"
                className="secondary-button"
                onClick={() => setEditingAsset(asset)}
              >
                Edit asset
              </button>
            )}
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
      <h3>Maintenance history</h3>
      <div className="resource-grid">
        {maintenance.map((record) => (
          <article className="resource-card" key={record.id}>
            <strong>
              {assets.find((asset) => asset.id === record.asset)?.asset_id ??
                "Asset"}{" "}
              — {record.kind}
            </strong>
            <span>
              {new Date(record.performed_at).toLocaleString()} ·{" "}
              {record.technician}
            </span>
            <p>{record.notes}</p>
            <small>
              Recorded by {record.recorded_by_username}
              {record.return_to_service ? " · Returned to service" : ""}
            </small>
          </article>
        ))}
      </div>
      <h3>Charging history</h3>
      <div className="resource-grid">
        {charging.map((record) => (
          <article className="resource-card" key={record.id}>
            <strong>
              {assets.find((asset) => asset.id === record.asset)?.asset_id ??
                "Asset"}
            </strong>
            <span>
              {new Date(record.started_at).toLocaleString()} —{" "}
              {record.completed_at
                ? new Date(record.completed_at).toLocaleString()
                : "In progress"}
            </span>
            <small>
              {record.notes || "No notes"} · Recorded by{" "}
              {record.recorded_by_username}
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
