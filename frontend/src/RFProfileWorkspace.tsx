import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  approveSubscriberProfileVersion,
  archiveSubscriberProfile,
  copySubscriberProfileVersion,
  createRFAnalysisInputSnapshot,
  createSubscriberProfile,
  listRFAnalysisInputSnapshots,
  listSubscriberProfiles,
  listSubscriberProfileVersions,
  updateSubscriberProfile,
  updateSubscriberProfileVersion,
} from "./api";
import type {
  EditableRFInputFields,
  Incident,
  RFAnalysisInputSnapshot,
  SubscriberProfile,
  SubscriberProfileType,
  SubscriberProfileVersion,
} from "./types";

const PROFILE_TYPES: {
  value: SubscriberProfileType;
  label: string;
}[] = [
  { value: "portable", label: "Portable" },
  { value: "mobile", label: "Mobile" },
  { value: "fixed", label: "Fixed" },
  { value: "configurable", label: "Configurable" },
];

const EMPTY_RF_INPUTS: EditableRFInputFields = {
  tx_frequency_hz: null,
  rx_frequency_hz: null,
  transmitter_power_w: null,
  effective_radiated_power_w: null,
  erp_source: "unknown",
  receiver_sensitivity_dbm: null,
  antenna_model: null,
  antenna_gain_db: null,
  antenna_gain_reference: "unknown",
  feed_line_type: null,
  feed_line_length_m: null,
  feed_line_loss_db: null,
  additional_system_loss_db: null,
  polarization: "unknown",
  frequency_band: "unknown",
  emission_designator: null,
  emission_bandwidth_hz: null,
  mounting_type: "unknown",
  antenna_center_agl_m: null,
  antenna_center_amsl_m: null,
  haat_m: null,
  input_basis: "unknown",
  notes: null,
};

type SimpleRFField = keyof EditableRFInputFields;

interface RFFieldDefinition {
  name: SimpleRFField;
  label: string;
  kind: "integer" | "decimal" | "text" | "textarea" | "select";
  options?: { value: string; label: string }[];
  help?: string;
}

interface RFFieldGroup {
  legend: string;
  description: string;
  fields: RFFieldDefinition[];
}

const RF_FIELD_GROUPS: RFFieldGroup[] = [
  {
    legend: "Transmitter and receiver",
    description:
      "Frequencies use integer hertz. Decimal quantities are preserved exactly as entered.",
    fields: [
      {
        name: "tx_frequency_hz",
        label: "Transmit frequency (Hz)",
        kind: "integer",
      },
      {
        name: "rx_frequency_hz",
        label: "Receive frequency (Hz)",
        kind: "integer",
      },
      {
        name: "transmitter_power_w",
        label: "Transmitter power (W)",
        kind: "decimal",
        help: "Radio output power before antenna-system gains and losses.",
      },
      {
        name: "effective_radiated_power_w",
        label: "Effective radiated power (ERP) (W)",
        kind: "decimal",
        help: "Sent only when ERP source is Entered directly. Calculated ERP and its path are server-computed.",
      },
      {
        name: "erp_source",
        label: "ERP source",
        kind: "select",
        options: [
          { value: "unknown", label: "Unknown (controlled value)" },
          { value: "entered", label: "Entered directly" },
          { value: "calculated", label: "Calculated by server" },
        ],
        help: "Record where the ERP value came from; do not infer a source.",
      },
      {
        name: "receiver_sensitivity_dbm",
        label: "Receiver sensitivity (dBm)",
        kind: "decimal",
      },
    ],
  },
  {
    legend: "Antenna and feed line",
    description:
      "Gain, loss, and reference values remain distinct so the server can validate the complete path.",
    fields: [
      {
        name: "antenna_model",
        label: "Antenna model",
        kind: "text",
      },
      {
        name: "antenna_gain_db",
        label: "Antenna gain (dB)",
        kind: "decimal",
      },
      {
        name: "antenna_gain_reference",
        label: "Antenna gain reference",
        kind: "select",
        options: [
          { value: "unknown", label: "Unknown (controlled value)" },
          { value: "dbi", label: "dBi" },
          { value: "dbd", label: "dBd" },
        ],
        help: "For example, record the applicable dBd or dBi reference.",
      },
      {
        name: "feed_line_type",
        label: "Feed-line type",
        kind: "text",
      },
      {
        name: "feed_line_length_m",
        label: "Feed-line length (m)",
        kind: "decimal",
      },
      {
        name: "feed_line_loss_db",
        label: "Feed-line loss (dB)",
        kind: "decimal",
      },
      {
        name: "additional_system_loss_db",
        label: "Additional system loss (dB)",
        kind: "decimal",
      },
      {
        name: "polarization",
        label: "Polarization",
        kind: "select",
        options: [
          { value: "unknown", label: "Unknown (controlled value)" },
          { value: "vertical", label: "Vertical" },
          { value: "horizontal", label: "Horizontal" },
          { value: "circular", label: "Circular" },
          { value: "mixed", label: "Mixed" },
        ],
      },
    ],
  },
  {
    legend: "Emission, mounting, and height",
    description:
      "AGL, AMSL, and HAAT are separate measurements and are never converted or substituted in the browser.",
    fields: [
      {
        name: "frequency_band",
        label: "Frequency band",
        kind: "select",
        options: [
          { value: "unknown", label: "Unknown (controlled value)" },
          { value: "vhf_low", label: "VHF low band" },
          { value: "vhf_high", label: "VHF high band" },
          { value: "uhf", label: "UHF" },
          { value: "700", label: "700 MHz" },
          { value: "800", label: "800 MHz" },
          { value: "900", label: "900 MHz" },
          { value: "other", label: "Other" },
        ],
      },
      {
        name: "emission_designator",
        label: "Emission designator",
        kind: "text",
      },
      {
        name: "emission_bandwidth_hz",
        label: "Emission bandwidth (Hz)",
        kind: "integer",
      },
      {
        name: "mounting_type",
        label: "Mounting type",
        kind: "select",
        options: [
          { value: "unknown", label: "Unknown (controlled value)" },
          { value: "handheld", label: "Handheld" },
          { value: "vehicle", label: "Vehicle" },
          { value: "structure", label: "Structure" },
          { value: "tower", label: "Tower" },
          { value: "mast", label: "Mast" },
          { value: "other", label: "Other" },
        ],
      },
      {
        name: "antenna_center_agl_m",
        label: "Antenna center AGL (m)",
        kind: "decimal",
        help: "Height above ground level.",
      },
      {
        name: "antenna_center_amsl_m",
        label: "Antenna center AMSL (m)",
        kind: "decimal",
        help: "Height above mean sea level.",
      },
      {
        name: "haat_m",
        label: "Height above average terrain (HAAT) (m)",
        kind: "decimal",
      },
    ],
  },
  {
    legend: "Basis and notes",
    description:
      "Separate recorded facts from modeled assumptions and preserve supporting notes.",
    fields: [
      {
        name: "input_basis",
        label: "Input basis",
        kind: "select",
        options: [
          { value: "unknown", label: "Unknown (controlled value)" },
          { value: "recorded_fact", label: "Recorded fact" },
          { value: "modeled_assumption", label: "Modeled assumption" },
          { value: "mixed", label: "Mixed facts and assumptions" },
        ],
        help: "Identify recorded facts, modeled assumptions, and their sources.",
      },
      {
        name: "notes",
        label: "Notes",
        kind: "textarea",
      },
    ],
  },
];

function nullableString(data: FormData, name: string): string | null {
  const value = String(data.get(name) ?? "").trim();
  return value === "" ? null : value;
}

function nullableInteger(data: FormData, name: string): number | null {
  const value = nullableString(data, name);
  return value === null ? null : Number(value);
}

function controlledChoice<T extends string>(data: FormData, name: string): T {
  return String(data.get(name) ?? "unknown") as T;
}

function rfInputsFromForm(data: FormData): EditableRFInputFields {
  const erpSource = controlledChoice<EditableRFInputFields["erp_source"]>(
    data,
    "erp_source",
  );
  return {
    tx_frequency_hz: nullableInteger(data, "tx_frequency_hz"),
    rx_frequency_hz: nullableInteger(data, "rx_frequency_hz"),
    transmitter_power_w: nullableString(data, "transmitter_power_w"),
    effective_radiated_power_w:
      erpSource === "entered"
        ? nullableString(data, "effective_radiated_power_w")
        : null,
    erp_source: erpSource,
    receiver_sensitivity_dbm: nullableString(data, "receiver_sensitivity_dbm"),
    antenna_model: nullableString(data, "antenna_model"),
    antenna_gain_db: nullableString(data, "antenna_gain_db"),
    antenna_gain_reference: controlledChoice(
      data,
      "antenna_gain_reference",
    ) as EditableRFInputFields["antenna_gain_reference"],
    feed_line_type: nullableString(data, "feed_line_type"),
    feed_line_length_m: nullableString(data, "feed_line_length_m"),
    feed_line_loss_db: nullableString(data, "feed_line_loss_db"),
    additional_system_loss_db: nullableString(
      data,
      "additional_system_loss_db",
    ),
    polarization: controlledChoice(
      data,
      "polarization",
    ) as EditableRFInputFields["polarization"],
    frequency_band: controlledChoice(
      data,
      "frequency_band",
    ) as EditableRFInputFields["frequency_band"],
    emission_designator: nullableString(data, "emission_designator"),
    emission_bandwidth_hz: nullableInteger(data, "emission_bandwidth_hz"),
    mounting_type: controlledChoice(
      data,
      "mounting_type",
    ) as EditableRFInputFields["mounting_type"],
    antenna_center_agl_m: nullableString(data, "antenna_center_agl_m"),
    antenna_center_amsl_m: nullableString(data, "antenna_center_amsl_m"),
    haat_m: nullableString(data, "haat_m"),
    input_basis: controlledChoice(
      data,
      "input_basis",
    ) as EditableRFInputFields["input_basis"],
    notes: nullableString(data, "notes"),
  };
}

function validateRFInputs(inputs: EditableRFInputFields): void {
  if (inputs.notes !== null) return;
  const reasons: string[] = [];
  if (inputs.erp_source === "entered") {
    reasons.push("ERP source is Entered directly");
  }
  if (inputs.input_basis === "mixed") {
    reasons.push("input basis is Mixed facts and assumptions");
  }
  if (reasons.length > 0) {
    throw new Error(`Notes are required when ${reasons.join(" and when ")}.`);
  }
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

export function RFProfileWorkspace({ incident }: { incident?: Incident }) {
  const [profiles, setProfiles] = useState<SubscriberProfile[]>([]);
  const [versions, setVersions] = useState<SubscriberProfileVersion[]>([]);
  const [snapshots, setSnapshots] = useState<RFAnalysisInputSnapshot[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState("");
  const [selectedVersionId, setSelectedVersionId] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const canView = incident?.permissions.includes("rf.view") ?? false;
  const canEdit = incident?.permissions.includes("rf.edit") ?? false;
  const canApprove = incident?.permissions.includes("rf.approve") ?? false;

  const refreshIncidentData = useCallback(
    async (preferredProfileId?: string) => {
      if (!incident || !canView) return;
      const [profileItems, snapshotItems] = await Promise.all([
        listSubscriberProfiles(incident.id),
        listRFAnalysisInputSnapshots(incident.id),
      ]);
      setProfiles(profileItems);
      setSnapshots(snapshotItems);
      setSelectedProfileId((current) => {
        const preferred = preferredProfileId ?? current;
        return profileItems.some((profile) => profile.id === preferred)
          ? preferred
          : (profileItems[0]?.id ?? "");
      });
    },
    [canView, incident],
  );

  const refreshVersions = useCallback(
    async (profileId: string, preferredVersionId?: string) => {
      const items = await listSubscriberProfileVersions(profileId);
      const ordered = [...items].sort((a, b) => b.number - a.number);
      setVersions(ordered);
      setSelectedVersionId((current) => {
        const preferred = preferredVersionId ?? current;
        if (ordered.some((version) => version.id === preferred)) {
          return preferred;
        }
        return (
          ordered.find((version) => version.status === "draft")?.id ??
          ordered[0]?.id ??
          ""
        );
      });
    },
    [],
  );

  useEffect(() => {
    setProfiles([]);
    setVersions([]);
    setSnapshots([]);
    setSelectedProfileId("");
    setSelectedVersionId("");
    setMessage("");
    setError("");
    if (!incident || !canView) return;
    void refreshIncidentData().catch((caught) => {
      setError(errorMessage(caught, "Unable to load RF subscriber profiles."));
    });
  }, [canView, incident, refreshIncidentData]);

  useEffect(() => {
    setVersions([]);
    setSelectedVersionId("");
    if (!selectedProfileId) return;
    void refreshVersions(selectedProfileId).catch((caught) => {
      setError(errorMessage(caught, "Unable to load profile versions."));
    });
  }, [refreshVersions, selectedProfileId]);

  const selectedProfile = profiles.find(
    (profile) => profile.id === selectedProfileId,
  );
  const selectedVersion = versions.find(
    (version) => version.id === selectedVersionId,
  );
  const versionLocked =
    selectedVersion?.is_locked || selectedVersion?.status === "approved";
  const mayEditVersion =
    Boolean(selectedVersion) &&
    canEdit &&
    !versionLocked &&
    !selectedProfile?.archived_at;

  const orderedSnapshots = useMemo(
    () =>
      [...snapshots].sort((a, b) =>
        (b.created_at ?? "").localeCompare(a.created_at ?? ""),
      ),
    [snapshots],
  );

  async function handleCreateProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!incident || !canEdit) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true);
    try {
      const profile = await createSubscriberProfile({
        incident: incident.id,
        name: String(data.get("name")).trim(),
        profile_type: String(data.get("profile_type")) as SubscriberProfileType,
        description: String(data.get("description")).trim(),
        initial_version: { ...EMPTY_RF_INPUTS },
      });
      form.reset();
      await refreshIncidentData(profile.id);
      setMessage(`Created ${profile.name} with an explicit-unknown draft.`);
      setError("");
    } catch (caught) {
      setError(errorMessage(caught, "Unable to create subscriber profile."));
    } finally {
      setBusy(false);
    }
  }

  async function handleMetadata(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedProfile || !canEdit) return;
    const data = new FormData(event.currentTarget);
    setBusy(true);
    try {
      await updateSubscriberProfile(selectedProfile.id, {
        name: String(data.get("name")).trim(),
        profile_type: String(data.get("profile_type")) as SubscriberProfileType,
        description: String(data.get("description")).trim(),
      });
      await refreshIncidentData(selectedProfile.id);
      setMessage("Profile metadata saved.");
      setError("");
    } catch (caught) {
      setError(errorMessage(caught, "Unable to update profile metadata."));
    } finally {
      setBusy(false);
    }
  }

  async function handleVersion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedProfile || !selectedVersion || !mayEditVersion) return;
    setBusy(true);
    try {
      const inputs = rfInputsFromForm(new FormData(event.currentTarget));
      validateRFInputs(inputs);
      const updated = await updateSubscriberProfileVersion(
        selectedVersion.id,
        inputs,
      );
      await refreshVersions(selectedProfile.id, updated.id);
      setMessage(`Saved draft version ${updated.number}.`);
      setError("");
    } catch (caught) {
      setError(errorMessage(caught, "Unable to save RF input fields."));
    } finally {
      setBusy(false);
    }
  }

  async function handleCopyVersion() {
    if (!selectedProfile || !selectedVersion || !canEdit) return;
    setBusy(true);
    try {
      const copied = await copySubscriberProfileVersion(selectedVersion.id);
      await refreshVersions(selectedProfile.id, copied.id);
      setMessage(`Copied approved version ${selectedVersion.number} to draft.`);
      setError("");
    } catch (caught) {
      setError(errorMessage(caught, "Unable to copy the approved version."));
    } finally {
      setBusy(false);
    }
  }

  async function handleApproveVersion() {
    if (!selectedProfile || !selectedVersion || !canApprove) return;
    if (
      !window.confirm(
        `Approve and lock version ${selectedVersion.number}? Later changes require a copied draft.`,
      )
    ) {
      return;
    }
    setBusy(true);
    try {
      const approved = await approveSubscriberProfileVersion(
        selectedVersion.id,
      );
      await refreshVersions(selectedProfile.id, approved.id);
      setMessage(`Approved and locked version ${approved.number}.`);
      setError("");
    } catch (caught) {
      setError(errorMessage(caught, "Unable to approve the profile version."));
    } finally {
      setBusy(false);
    }
  }

  async function handleSnapshot(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!incident || !selectedVersion || !canApprove) return;
    const form = event.currentTarget;
    const label = String(new FormData(form).get("label")).trim();
    setBusy(true);
    try {
      await createRFAnalysisInputSnapshot(selectedVersion.id, label);
      setSnapshots(await listRFAnalysisInputSnapshots(incident.id));
      form.reset();
      setMessage(`Created immutable snapshot “${label}”.`);
      setError("");
    } catch (caught) {
      setError(errorMessage(caught, "Unable to create the input snapshot."));
    } finally {
      setBusy(false);
    }
  }

  async function handleArchiveProfile() {
    if (!selectedProfile || !canEdit) return;
    if (
      !window.confirm(
        `Archive ${selectedProfile.name}? Its versions and audit history will be retained.`,
      )
    ) {
      return;
    }
    setBusy(true);
    try {
      await archiveSubscriberProfile(selectedProfile.id);
      await refreshIncidentData();
      setMessage(`Archived ${selectedProfile.name}.`);
      setError("");
    } catch (caught) {
      setError(errorMessage(caught, "Unable to archive the profile."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rf-profile-panel" aria-labelledby="rf-profile-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Versioned RF input records</p>
          <h2 id="rf-profile-heading">Subscriber RF profiles</h2>
        </div>
        {canView && <span className="count">{profiles.length}</span>}
      </div>

      <div className="rf-human-gate" role="note">
        <strong>
          Provisional · synthetic or explicitly approved data only
        </strong>
        <p>
          These records support planning decisions; they are not coverage
          predictions or authorization to operate. Qualified COML, COMT, COMC,
          and RF engineering practitioners must approve the fields, units,
          ranges, and assumptions before operational use.
        </p>
      </div>

      {!incident ? (
        <p className="empty">Select an incident to view its RF profiles.</p>
      ) : !canView ? (
        <p className="empty">
          You do not have <code>rf.view</code> access for this incident.
        </p>
      ) : (
        <>
          <p className="rf-unknown-note" id="rf-unknown-semantics">
            <strong>Unknown values:</strong> a blank nullable measurement or
            text field is sent as <code>null</code> and means explicitly
            unknown. Controlled fields use the explicit “Unknown” choice. Zero
            is a recorded value and never means unknown, although field range
            rules may reject it. Units are shown on every measured field.
          </p>

          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          {message && (
            <p className="rf-message" role="status" aria-live="polite">
              {message}
            </p>
          )}

          {canEdit && (
            <details className="rf-create-profile">
              <summary>Create subscriber profile</summary>
              <form className="rf-metadata-form" onSubmit={handleCreateProfile}>
                <label>
                  Profile name
                  <input name="name" required maxLength={160} />
                </label>
                <label>
                  Profile type
                  <select name="profile_type" required defaultValue="portable">
                    {PROFILE_TYPES.map((profileType) => (
                      <option key={profileType.value} value={profileType.value}>
                        {profileType.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="rf-wide-field">
                  Description
                  <textarea name="description" rows={2} />
                </label>
                <p className="rf-wide-field rf-form-note">
                  The initial draft records every RF value as explicitly
                  unknown. Enter synthetic or approved values after creation.
                </p>
                <button type="submit" disabled={busy}>
                  Create profile and draft
                </button>
              </form>
            </details>
          )}

          {profiles.length === 0 ? (
            <p className="empty">No RF subscriber profiles are available.</p>
          ) : (
            <>
              <div className="rf-selectors">
                <label>
                  Subscriber profile
                  <select
                    value={selectedProfileId}
                    onChange={(event) =>
                      setSelectedProfileId(event.target.value)
                    }
                  >
                    {profiles.map((profile) => (
                      <option key={profile.id} value={profile.id}>
                        {profile.name} ·{" "}
                        {
                          PROFILE_TYPES.find(
                            (item) => item.value === profile.profile_type,
                          )?.label
                        }
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Profile version
                  <select
                    value={selectedVersionId}
                    onChange={(event) =>
                      setSelectedVersionId(event.target.value)
                    }
                    disabled={versions.length === 0}
                  >
                    {versions.map((version) => (
                      <option key={version.id} value={version.id}>
                        Version {version.number} · {version.status}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              {selectedProfile && (
                <form
                  className="rf-metadata-form"
                  key={selectedProfile.id}
                  onSubmit={handleMetadata}
                >
                  <h3 className="rf-wide-field">Profile metadata</h3>
                  <label>
                    Profile name
                    <input
                      name="name"
                      defaultValue={selectedProfile.name}
                      readOnly={
                        !canEdit || Boolean(selectedProfile.archived_at)
                      }
                      required
                    />
                  </label>
                  <label>
                    Profile type
                    <select
                      name="profile_type"
                      defaultValue={selectedProfile.profile_type}
                      disabled={
                        !canEdit || Boolean(selectedProfile.archived_at)
                      }
                    >
                      {PROFILE_TYPES.map((profileType) => (
                        <option
                          key={profileType.value}
                          value={profileType.value}
                        >
                          {profileType.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="rf-wide-field">
                    Description
                    <textarea
                      name="description"
                      defaultValue={selectedProfile.description}
                      readOnly={
                        !canEdit || Boolean(selectedProfile.archived_at)
                      }
                      rows={2}
                    />
                  </label>
                  {canEdit && !selectedProfile.archived_at && (
                    <div className="button-row rf-wide-field">
                      <button type="submit" disabled={busy}>
                        Save profile metadata
                      </button>
                      <button
                        type="button"
                        className="secondary-button"
                        disabled={busy}
                        onClick={() => void handleArchiveProfile()}
                      >
                        Archive profile
                      </button>
                    </div>
                  )}
                  {selectedProfile.archived_at && (
                    <p className="rf-wide-field rf-form-note">
                      Archived{" "}
                      {new Date(selectedProfile.archived_at).toLocaleString()}.
                      This record is read-only.
                    </p>
                  )}
                </form>
              )}

              {!selectedVersion ? (
                <p className="empty">This profile has no available versions.</p>
              ) : (
                <form
                  className="rf-version-form"
                  key={selectedVersion.id}
                  onSubmit={handleVersion}
                >
                  <div className="revision-bar">
                    <strong>Version {selectedVersion.number}</strong>
                    <span className={`status ${selectedVersion.status}`}>
                      {selectedVersion.status}
                    </span>
                    {versionLocked && (
                      <span className="rf-read-only">Read-only and locked</span>
                    )}
                  </div>

                  {RF_FIELD_GROUPS.map((group) => (
                    <fieldset key={group.legend}>
                      <legend>{group.legend}</legend>
                      <p>{group.description}</p>
                      <div className="rf-field-grid">
                        {group.fields.map((field) => {
                          const value = selectedVersion[field.name];
                          const defaultValue =
                            typeof value === "number"
                              ? String(value)
                              : (value ?? "");
                          const inputProps = {
                            name: field.name,
                            defaultValue,
                            placeholder: "Unknown (null)",
                            readOnly: !mayEditVersion,
                            "aria-label": field.label,
                            "aria-describedby": "rf-unknown-semantics",
                            autoComplete: "off",
                          };
                          return (
                            <label
                              className={
                                field.kind === "textarea"
                                  ? "rf-wide-field"
                                  : undefined
                              }
                              key={field.name}
                            >
                              {field.label}
                              {field.kind === "select" ? (
                                <select
                                  name={field.name}
                                  defaultValue={defaultValue}
                                  disabled={!mayEditVersion}
                                  aria-label={field.label}
                                  aria-describedby="rf-unknown-semantics"
                                >
                                  {field.options?.map((option) => (
                                    <option
                                      key={option.value}
                                      value={option.value}
                                    >
                                      {option.label}
                                    </option>
                                  ))}
                                </select>
                              ) : field.kind === "textarea" ? (
                                <textarea {...inputProps} rows={3} />
                              ) : (
                                <input
                                  {...inputProps}
                                  type={
                                    field.kind === "integer" ? "number" : "text"
                                  }
                                  inputMode={
                                    field.kind === "integer"
                                      ? "numeric"
                                      : field.kind === "decimal"
                                        ? "decimal"
                                        : undefined
                                  }
                                  min={
                                    field.kind === "integer" ? "1" : undefined
                                  }
                                  step={
                                    field.kind === "integer" ? "1" : undefined
                                  }
                                />
                              )}
                              {field.help && <small>{field.help}</small>}
                            </label>
                          );
                        })}
                      </div>
                    </fieldset>
                  ))}

                  {(selectedVersion.erp_calculation_path ||
                    selectedVersion.input_snapshot ||
                    selectedVersion.input_sha256) && (
                    <details className="rf-version-provenance">
                      <summary>
                        Server calculation path and immutable provenance
                      </summary>
                      <p>
                        ERP calculation path is computed by the server from the
                        recorded source and component inputs. It is read-only.
                      </p>
                      {selectedVersion.erp_calculation_path && (
                        <pre>
                          {JSON.stringify(
                            selectedVersion.erp_calculation_path,
                            null,
                            2,
                          )}
                        </pre>
                      )}
                      <p>
                        SHA-256:{" "}
                        <code>
                          {selectedVersion.input_sha256 ?? "Not captured"}
                        </code>
                      </p>
                      {selectedVersion.input_snapshot && (
                        <pre>
                          {JSON.stringify(
                            selectedVersion.input_snapshot,
                            null,
                            2,
                          )}
                        </pre>
                      )}
                    </details>
                  )}

                  <div className="button-row">
                    {mayEditVersion && (
                      <button type="submit" disabled={busy}>
                        Save RF draft
                      </button>
                    )}
                    {versionLocked &&
                      canEdit &&
                      !selectedProfile?.archived_at && (
                        <button
                          type="button"
                          className="secondary-button"
                          disabled={busy}
                          onClick={() => void handleCopyVersion()}
                        >
                          Copy approved version to new draft
                        </button>
                      )}
                    {!versionLocked &&
                      canApprove &&
                      !selectedProfile?.archived_at && (
                        <button
                          type="button"
                          className="secondary-button"
                          disabled={busy}
                          onClick={() => void handleApproveVersion()}
                        >
                          Approve and lock RF version
                        </button>
                      )}
                  </div>
                </form>
              )}

              {selectedVersion?.status === "approved" && canApprove && (
                <form className="rf-snapshot-form" onSubmit={handleSnapshot}>
                  <h3>Create immutable analysis snapshot</h3>
                  <p>
                    A snapshot preserves the exact approved profile inputs and
                    digest for later analysis records.
                  </p>
                  <label>
                    Snapshot label
                    <input
                      name="label"
                      placeholder="Synthetic exercise baseline"
                      required
                      maxLength={160}
                    />
                  </label>
                  <button type="submit" disabled={busy}>
                    Create immutable snapshot
                  </button>
                </form>
              )}
            </>
          )}

          <section
            className="rf-snapshot-list"
            aria-labelledby="rf-snapshot-heading"
          >
            <h3 id="rf-snapshot-heading">Incident input snapshots</h3>
            {orderedSnapshots.length === 0 ? (
              <p className="empty">No immutable RF snapshots are available.</p>
            ) : (
              orderedSnapshots.map((snapshot) => (
                <article key={snapshot.id}>
                  <strong>{snapshot.label}</strong>
                  <span>
                    Profile version {snapshot.profile_version} · immutable
                  </span>
                  <code>{snapshot.input_sha256}</code>
                </article>
              ))
            )}
          </section>
        </>
      )}
    </section>
  );
}
