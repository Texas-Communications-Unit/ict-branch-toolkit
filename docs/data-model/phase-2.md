# Phase 2 RF analysis and terrain data model

## Status and boundary

P2.1 implements incident-scoped, versioned subscriber profiles and immutable RF analysis input
snapshots. P2.2 adds source-aware elevation snapshots and reproducible HAAT calculations. Both
include migrations, API/OpenAPI, backend permissions, unit/integration tests, and authenticated
synthetic browser workflows. P2.3 adds an immutable, explainable `CoverageEstimate` aggregate and
a replaceable provisional calculation-engine boundary. P2.4 adds immutable separate-direction
talk-out, talk-in, and probable two-way analysis.

The implemented aggregates are:

- `SubscriberProfile`;
- `SubscriberProfileVersion`;
- `RFAnalysisInputSnapshot`;
- `ElevationSnapshot`;
- `HAATCalculation`;
- `CoverageEstimate`; and
- `DirectionalCoverageAnalysis`.

The first three records are the P2.1 input aggregate. The P2.2 terrain aggregate references an
exact site and immutable approved RF input snapshot, including its profile version, but is not a
propagation result. Future coverage estimates must reference the exact approved RF input and
applicable elevation/HAAT result rather than resolving a current mutable record.

P2.3 now follows that rule: every estimate references the exact approved RF input snapshot and
complete approved HAAT calculation, then preserves the site coordinates, engine and preset
versions, assumptions, intermediate values, geometry, warnings, explanation, and integrity
digests used for its result.

P2.4 references that same infrastructure evidence plus one distinct approved subscriber snapshot.
It preserves talk-out and talk-in separately, derives probable two-way distance only from their
supported overlap, and stores the limiting path, exact engine/preset/rule versions, path evidence,
geometry, warnings, exclusions, explanations, and integrity digests.

Only synthetic or explicitly approved data may be used. All field enumerations, numerical ranges,
cross-field rules, calculation conventions, and subscriber assumptions are provisional. **No
operational default is approved.** Qualified COML, COMT, COMC, and RF engineering practitioners
must approve them before operational suitability is claimed.

See [ADR-0008](../adr/0008-versioned-rf-analysis-inputs-and-subscriber-profiles.md) for the
architectural decision and calculation boundary.

## Unit and unknown rules

- `tx_frequency_hz`, `rx_frequency_hz`, and `emission_bandwidth_hz` use integer hertz (`Hz`).
- `transmitter_power_w` and `effective_radiated_power_w` use decimal watts (`W`).
- `feed_line_length_m`, `antenna_center_agl_m`, `antenna_center_amsl_m`, and `haat_m` use decimal
  meters (`m`).
- `receiver_sensitivity_dbm` uses `dBm`, explicitly referenced to one milliwatt.
- `antenna_gain_db` uses `dB` with `antenna_gain_reference` set to `dbi`, `dbd`, or `unknown`.
- `feed_line_loss_db` and `additional_system_loss_db` are power-like loss ratios in `dB`.
- Dates/times are server-assigned, timezone-aware UTC instants.

[NIST SP 811 Chapter 4](https://www.nist.gov/pml/special-publication-811/nist-guide-si-chapter-4-two-classes-si-units-and-si-prefixes)
identifies hertz, watt, and meter within the SI system.
[NIST SP 811 Chapter 5](https://www.nist.gov/pml/special-publication-811/nist-guide-si-chapter-5-units-outside-si)
requires a stated logarithmic reference and uses `10^(dB/10)` for power-like ratios. The ERP/gain
reference distinction follows the
[FCC definition](https://docs.fcc.gov/public/attachments/DOC-396579A1.pdf).

Unknown values are explicit:

- nullable numeric fields use `null`;
- nullable version text fields use `null`;
- the profile description uses blank;
- controlled fields use their `unknown` choice.

Callers use `null` for an unknown nullable measurement or version text. The API normalizes blank
nullable version text and the browser's blank nullable fields to `null`. Unknown never means zero
and never authorizes a default. Zero remains a submitted value only where the provisional
validator allows it. Display rounding does not alter canonical persisted decimals.

## Enumerations

These are implemented controlled values, not approved operational assumptions.

| Field                    | Values                                                                  |
| ------------------------ | ----------------------------------------------------------------------- |
| `profile_type`           | `portable`, `mobile`, `fixed`, `cache`, `gateway`, `configurable`       |
| `status`                 | `draft`, `approved`                                                     |
| `erp_source`             | `unknown`, `entered`, `calculated`                                      |
| `antenna_gain_reference` | `unknown`, `dbi`, `dbd`                                                 |
| `polarization`           | `unknown`, `vertical`, `horizontal`, `circular`, `mixed`                |
| `frequency_band`         | `unknown`, `vhf_low`, `vhf_high`, `uhf`, `700`, `800`, `900`, `other`   |
| `mounting_type`          | `unknown`, `handheld`, `vehicle`, `structure`, `tower`, `mast`, `other` |
| `input_basis`            | `unknown`, `recorded_fact`, `modeled_assumption`, `mixed`               |

`input_basis` describes the complete profile version, not each field. `recorded_fact` means
populated values are represented as measured, observed, manufacturer-stated, or obtained from an
approved record. `modeled_assumption` means they are deliberate modeling assumptions. `mixed`
requires the existing `notes` field to identify which field groups use each basis. P2.1 does not
claim per-field provenance.

## `SubscriberProfile`

One stable profile identity groups all numbered versions. It is incident-scoped and archived
rather than deleted.

| Field          | Type/unknown behavior                    | Meaning                                                                                                    |
| -------------- | ---------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `id`           | UUID, required                           | Stable profile identifier.                                                                                 |
| `incident`     | protected incident foreign key, required | Owning incident and authorization boundary.                                                                |
| `name`         | text, required, maximum 160 characters   | Minimal profile label; not an equipment serial or owner.                                                   |
| `profile_type` | controlled value, required               | `portable`, `mobile`, `fixed`, `cache`, `gateway`, or `configurable`; no type is operationally preferred. |
| `description`  | text, blank allowed                      | Minimal synthetic/approved purpose description; blank means unknown/not provided.                          |
| `created_by`   | protected user foreign key, required     | Creating actor.                                                                                            |
| `created_at`   | UTC timestamp, required                  | Server-assigned creation time.                                                                             |
| `updated_at`   | UTC timestamp, required                  | Server-assigned last-change time.                                                                          |
| `archived_at`  | UTC timestamp, nullable                  | Archive time; `null` means active.                                                                         |

The profile API also exposes `initial_version`, a required write-only first-draft object on create,
and `versions`, a read-only nested list of its numbered versions. `initial_version` is rejected on
profile updates. `id`, `versions`, `created_by`, timestamps, and `archived_at` are read-only;
archival uses the dedicated action. The owning incident cannot be changed after creation.

Hard deletion is rejected. Archival preserves versions, snapshots, approvals, and audit history.

## `SubscriberProfileVersion`

Each version is one complete RF input record. `(profile, number)` is unique. Only `draft` versions
are editable; `approved` versions are immutable and retained.

### Identity, lifecycle, basis, and snapshot fields

| Field                  | Type/unknown behavior                             | Meaning                                                                                    |
| ---------------------- | ------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| `id`                   | UUID, required                                    | Version identifier.                                                                        |
| `profile`              | protected profile foreign key, required           | Parent `SubscriberProfile`.                                                                |
| `number`               | positive integer, required                        | Monotonic profile-local version number.                                                    |
| `status`               | `draft` or `approved`, required                   | Approval/immutability state.                                                               |
| `is_locked`            | boolean, read-only                                | `true` exactly when approved.                                                              |
| `input_basis`          | controlled value, required; defaults to `unknown` | Whole-version fact/assumption classification. The `unknown` sentinel is not an RF default. |
| `notes`                | text, nullable                                    | Minimized non-sensitive source/method context; explains mixed basis; `null` is unknown.    |
| `erp_calculation_path` | structured JSON, server-controlled                | Records the server-selected unknown, entered, or calculated method and its preserved path. |
| `input_snapshot`       | structured JSON, read-only; empty on a draft      | Canonical approved values, units, enum values, basis, notes, and calculation path.         |
| `input_sha256`         | lowercase SHA-256, read-only                      | Digest of the canonical approved `input_snapshot`; blank on a draft.                       |
| `created_by`           | protected user foreign key, required              | Version creator.                                                                           |
| `approved_by`          | protected user foreign key, nullable              | Approver; required on an approved version.                                                 |
| `approved_at`          | UTC timestamp, nullable                           | Server-assigned approval time; required on an approved version.                            |
| `created_at`           | UTC timestamp, required                           | Server-assigned creation time.                                                             |
| `updated_at`           | UTC timestamp, required                           | Server-assigned last-change time.                                                          |

Approval atomically creates the canonical snapshot/digest and approval evidence. A draft has no
approval actor/time or digest. Copying an approved version creates the next draft without changing
the approved source. Only an approved version can be copied, and a profile cannot have a second
editable draft.

The 23 editable input fields are writable only on drafts. Version identity, number, status,
calculation path, snapshot, digest, creator/approver metadata, timestamps, and `is_locked` are
read-only. New versions come from the profile's `initial_version` or by copying an approved
version; there is no independent caller-selected version-number create operation.

### Transmitter, receiver, ERP, antenna, feed-line, emission, and height fields

| Field                        | Canonical type/unit and unknown behavior  | Meaning                                                                                      |
| ---------------------------- | ----------------------------------------- | -------------------------------------------------------------------------------------------- |
| `tx_frequency_hz`            | integer `Hz`, nullable                    | Transmit frequency; `null` is explicitly unknown.                                            |
| `rx_frequency_hz`            | integer `Hz`, nullable                    | Receive frequency; `null` is explicitly unknown.                                             |
| `transmitter_power_w`        | decimal `W` to 6 places, nullable         | Radio output power at the documented transmitter reference point; never synonymous with ERP. |
| `effective_radiated_power_w` | decimal `W` to 6 places, nullable         | Entered or server-calculated ERP according to `erp_source`; `null` is unknown.               |
| `erp_source`                 | `unknown`, `entered`, or `calculated`     | Whether ERP is absent, supplied from a reviewed source, or derived by the server.            |
| `receiver_sensitivity_dbm`   | decimal `dBm` to 3 places, nullable       | Receiver threshold at its documented condition and one-milliwatt reference.                  |
| `antenna_model`              | text, nullable, maximum 200 characters    | Minimal generic model/configuration label; no serial, owner, or private asset identifier.    |
| `antenna_gain_db`            | signed decimal `dB` to 3 places, nullable | Antenna power gain whose reference is separately recorded.                                   |
| `antenna_gain_reference`     | `unknown`, `dbi`, or `dbd`                | Reference for `antenna_gain_db`; unknown prevents calculated ERP.                            |
| `feed_line_type`             | text, nullable, maximum 160 characters    | Minimal generic feed-line type/configuration.                                                |
| `feed_line_length_m`         | decimal `m` to 3 places, nullable         | Feed-line length; no loss is inferred from type/length.                                      |
| `feed_line_loss_db`          | decimal `dB` to 3 places, nullable        | Total documented feed-line power loss at the applicable condition.                           |
| `additional_system_loss_db`  | decimal `dB` to 3 places, nullable        | Other documented system loss; no connector/amplifier subfields are implied.                  |
| `polarization`               | controlled value                          | Explicit polarization or `unknown`; no band-based default.                                   |
| `frequency_band`             | controlled value                          | Descriptive band category or `unknown`; exact frequencies remain authoritative inputs.       |
| `emission_designator`        | text, nullable, maximum 32 characters     | Entered emission designator; not derived from band/mode.                                     |
| `emission_bandwidth_hz`      | integer `Hz`, nullable                    | Explicit emission bandwidth; `null` is unknown.                                              |
| `mounting_type`              | controlled value                          | Explicit mounting category or `unknown`; no profile-based default.                           |
| `antenna_center_agl_m`       | decimal `m` to 3 places, nullable         | Antenna center above the local ground reference.                                             |
| `antenna_center_amsl_m`      | signed decimal `m` to 3 places, nullable  | Antenna-center elevation above mean sea level.                                               |
| `haat_m`                     | signed decimal `m` to 3 places, nullable  | Height above average terrain under a separately documented method/source.                    |

The model deliberately omits equipment serial numbers, asset IDs, owner contacts, credentials,
protected channel details, private infrastructure identifiers, and unrestricted source uploads.

## Implemented provisional validation ranges

These are broad defensive data-quality guards. They are **provisional**, are not approved
equipment capability limits or propagation-model ranges, and must not be used as subscriber
defaults.

| Fields                                                        | Implemented range                             |
| ------------------------------------------------------------- | --------------------------------------------- |
| `tx_frequency_hz`, `rx_frequency_hz`, `emission_bandwidth_hz` | `1` through `1,000,000,000,000 Hz` when known |
| `transmitter_power_w`, `effective_radiated_power_w`           | `0` through `10,000,000 W` when known         |
| `receiver_sensitivity_dbm`                                    | `-300` through `100 dBm` when known           |
| `antenna_gain_db`                                             | `-200` through `200 dB` when known            |
| `feed_line_length_m`                                          | `0` through `1,000,000 m` when known          |
| `feed_line_loss_db`, `additional_system_loss_db`              | `0` through `1,000 dB` when known             |
| `antenna_center_agl_m`                                        | `0` through `100,000 m` when known            |
| `antenna_center_amsl_m`, `haat_m`                             | `-100,000` through `100,000 m` when known     |

Cross-field behavior:

- `erp_source = unknown` does not substitute transmitter power for ERP.
- `erp_source = entered` preserves the entered ERP and requires source/method context in `notes`
  for qualified review.
- `erp_source = calculated` requires known transmitter power, both implemented loss fields,
  antenna gain, and a `dbi` or `dbd` gain reference.
- Missing calculated-ERP inputs reject the request and identify the missing fields; loss is not
  assumed to be zero.
- A gain value with `antenna_gain_reference = unknown` is not enough to calculate ERP.
- `input_basis = mixed` uses `notes` to explain the fact/assumption boundary.
- AGL, AMSL, and HAAT remain independent. No implemented rule derives or overwrites one from
  another.
- Approval requires consistent approval actor/time and a nonblank canonical input digest.

Qualified reviewers may tighten, expand, or reject these ranges and rules. Any approved change
requires updated migrations/validation, OpenAPI, tests, documentation, and a new calculation-method
version where results could change.

## ERP calculation path

The server-calculated path uses the exact known values:

```text
total_system_loss_db =
  feed_line_loss_db + additional_system_loss_db

antenna_input_power_w =
  transmitter_power_w * 10^(-total_system_loss_db / 10)

if antenna_gain_reference == "dbi":
  antenna_gain_dbd = antenna_gain_db - 2.15
else if antenna_gain_reference == "dbd":
  antenna_gain_dbd = antenna_gain_db

effective_radiated_power_w =
  antenna_input_power_w * 10^(antenna_gain_dbd / 10)
```

The `2.15 dB` dBi-to-dBd offset is a provisional prototype conversion convention pending
qualified review, not an FCC operational default. For the calculated method,
`erp_calculation_path` records:

- `method = calculated` and `method_version = erp-v1-provisional`;
- the exact formula string;
- `transmitter_power_w`, entered antenna gain, its original gain reference, and the applied
  dBi-to-dBd offset;
- normalized `antenna_gain_dbd`, both implemented loss inputs, `total_loss_db`,
  `antenna_input_power_w`, and `net_gain_db`; and
- `result_effective_radiated_power_w`.

Caller-supplied calculation JSON is not authoritative.

The FCC isotropic-reference distinction prevents an entered `dBi` gain from being treated as
dipole-referenced gain when the server calculates ERP.

For `erp_source = unknown`, the server records an unknown-method path and requires
`effective_radiated_power_w` to be `null`. For `erp_source = entered`, it records an entered-method
path and preserves the reviewed ERP rather than presenting it as server-derived. Callers cannot
write `erp_calculation_path`.

## AGL, AMSL, and HAAT

- `antenna_center_agl_m` is antenna-center distance above the local ground reference.
- `antenna_center_amsl_m` is antenna-center elevation above mean sea level.
- `haat_m` is antenna-center height relative to average terrain under a defined method.
- All may be unknown independently.
- P2.1 does not automatically derive or cross-correct these version fields.
- P2.2 creates a separate retained `HAATCalculation`; it does not silently overwrite the profile
  version's entered height fields.
- The P2.2 result preserves terrain source/version, site and profile input snapshots, sampling
  method, coordinates, datum transformation, exclusions, method version, and result digest.
- The implemented method and all validation ranges remain provisional and require the qualified
  human gate.

## `ElevationSnapshot`

An immutable elevation cache record belongs to one incident and radio site. It retains the exact
canonical radial query and samples rather than storing only a site elevation.

| Field group | Preserved evidence |
| --- | --- |
| Identity and scope | UUID, incident, radio site, creator, creation time |
| Cache identity | canonical query JSON and SHA-256 |
| Source | provider, dataset/product, source version or retrieval time, resolution, coverage |
| References | horizontal CRS, source vertical CRS, target vertical CRS, transformation path |
| Terms | permitted use and license/terms reference |
| Integrity | source content digest when supplied, canonical sample digest |
| State | `complete`, `partial`, `missing`, or `out_of_coverage`; expired records expose `stale` |
| Retention | retrieval and stale times, warnings, immutable sample snapshot |

Cache reuse requires the same incident, site, and query digest and an unexpired record. A forced
refresh creates another immutable snapshot. Stale records remain available as evidence but are not
reused for new work.

## `HAATCalculation`

Each retained calculation references one radio site, one immutable `RFAnalysisInputSnapshot` and
its approved subscriber profile version, and one elevation snapshot. Retry creates a new
calculation with `supersedes`; it never updates the previous result.

The calculation records:

- draft or approved/locked lifecycle and complete, partial, or unavailable result state;
- method and version;
- radial count, starting azimuth, exact generated azimuths, sample interval, distance limits, and
  endpoint behavior;
- coordinate earth model, datum transformation, exclusion rule, partial-result rule, and rounding;
- antenna AGL, site elevation, antenna AMSL, average terrain, and HAAT in meters;
- used/excluded sample counts, each exclusion, warnings, creator/approver evidence; and
- canonical result snapshot and SHA-256.

The approved RF input snapshot must contain explicit antenna-center AGL. Complete results may be
approved by an authorized reviewer. Partial and unavailable results remain visible but cannot be
approved.
One request is limited to 10,000 terrain samples as a provisional resource-safety guard; it is not
an operational method limit.

`haat-radial-average-v1-provisional` is a general planning radial-average terrain method. It is
not represented as the governing method for any FCC, NTIA, coordination, licensing, or
land-mobile-radio service. See [ADR-0009](../adr/0009-source-aware-elevation-and-reproducible-haat.md)
and the [operations guide](../operations/elevation-and-haat.md).

## `CoverageEstimate`

Each retained estimate references one incident, one radio site, one immutable approved
`RFAnalysisInputSnapshot`, and one complete approved `HAATCalculation`. It stores:

- draft or approved/locked lifecycle and `complete` or `unsupported` calculation state;
- selected environment, derived band group, engine/version, and preset/version;
- WGS 84 center coordinates;
- conservative, nominal, and optimistic integer-meter distances when complete;
- canonical input snapshot and SHA-256;
- model snapshot containing formulas, constants, assumptions, intermediate values, and limiting
  factors;
- warnings, exclusions, and a plain-language explanation;
- deterministic WGS 84 output geometry and canonical result SHA-256; and
- creator/approver identity and timestamps.

Complete results may be approved and locked. Unsupported results are retained without distances or
geometry and cannot be approved. All results are immutable after creation and cannot be deleted.
Changing a source input, engine version, preset version, environment, or site coordinate creates a
new record; it never rewrites an existing estimate.

The first engine is `fspl-horizon-v1-provisional`. Its band groups, environment margins,
receiver-height assumption, uncertainty, distance limits, rounding, and formulas require
qualified review and are not operational defaults. It is intentionally a single-path prototype;
P2.4 introduces separate talk-out, talk-in, and probable two-way analysis.

See
[ADR-0010](../adr/0010-provisional-explainable-coverage-estimates.md) and the
[coverage-estimate evaluation guide](../operations/coverage-estimates.md).

## `DirectionalCoverageAnalysis`

Each retained directional analysis references one complete approved infrastructure HAAT
calculation, its exact infrastructure RF input snapshot, and one distinct approved subscriber RF
input snapshot in the same incident. It stores:

- draft or approved/locked lifecycle and complete, unsupported, or no-overlap calculation state;
- selected environment and exact engine, preset, and directional-rule versions;
- separate talk-out and talk-in nominal distances;
- probable two-way distance derived from the smaller supported nominal path;
- the explicit limiting path;
- WGS 84 center and separate deterministic geometry for each supported path;
- canonical input, model, path-result, warning, exclusion, explanation, and digest evidence; and
- creator/approver identity and timestamps.

The initial `concentric-minimum-v1-provisional` rule requires cross-matched transmit/receive
frequencies. It does not average unequal paths or fabricate overlap when either direction is
unsupported. Manual rings and prior P2.3 estimates remain separate records and layers.

See [ADR-0011](../adr/0011-separate-directional-and-two-way-analysis.md) and the
[directional evaluation guide](../operations/directional-coverage-analysis.md).

## `FieldObservation` and `FieldObservationReview`

Each immutable observation belongs to one incident and references distinct approved
infrastructure and subscriber `RFAnalysisInputSnapshot` records. An optional approved
`CoverageEstimate` or `DirectionalCoverageAnalysis` preserves the modeled comparison source.

The observation stores:

- good, marginal, or failed-communications classification;
- measured, operator, imported, or modeled evidence type;
- bounded observation time window;
- explicit WGS 84 exact, pre-storage generalized, or pre-storage redacted location handling;
- optional direction and integer-meter path distance;
- minimized observer/source and collection method;
- bounded environment and measurement objects, notes, controlled quality flags, source ID and
  revision;
- correction linkage through one immutable `supersedes` relationship;
- exact approved RF and analysis source identities/digests;
- canonical input snapshot and SHA-256; and
- creator and creation time.

Generalized coordinates are rounded before the model, snapshot, audit event, or API response is
created. Redacted observations retain no coordinate or precision value. Raw coordinates are not
stored as a hidden companion field.

Each `FieldObservationReview` is an immutable append-only approval or exclusion decision with a
reason, reviewer, timestamp, evidence digest, and prior-review digest in its canonical evidence.
The latest decision is the effective review state. A correction does not alter the prior record,
and a superseded record cannot be newly approved.

## `CalibrationSet` and `CalibrationSetObservation`

Each calibration set is an immutable named version within one incident. Membership is preserved
through immutable links that capture each observation digest and effective review-evidence digest.
The set records:

- draft or approved/locked lifecycle and complete or insufficient-data state;
- exact algorithm/version, bounded parameters, baseline preset/version;
- minimized observation snapshot and aggregate digest;
- classification distribution, usable count, warnings, and explicit missing/outlier exclusions;
- incident-local recommended multiplier marked `not_promoted`;
- before/after mean absolute and percentage error;
- canonical result snapshot and digest; and
- creator/approver identity and timestamps.

`observation-envelope-v1-provisional` fits the median of bounded positive
measured-to-predicted distance ratios and requires at least three usable observations by default.
It is an explainable prototype, not a scientific propagation-validation method. Approval fails
unless the exact algorithm is server-allowlisted and all linked observation and review evidence is
still current. Approval never writes to the coverage engine's organization defaults.

See [ADR-0012](../adr/0012-field-observations-and-incident-local-calibration.md) and the
[field observation and calibration guide](../operations/field-observations-and-calibration.md).

## `RFAnalysisInputSnapshot`

This immutable named record copies one approved profile version's canonical snapshot for later
analysis use. Creating it does not create or approve a propagation result.

| Field             | Type/unknown behavior                            | Meaning                                                                        |
| ----------------- | ------------------------------------------------ | ------------------------------------------------------------------------------ |
| `id`              | UUID, required                                   | Snapshot identifier.                                                           |
| `incident`        | protected incident foreign key, required         | Defense-in-depth incident boundary; must match the profile version's incident. |
| `profile_version` | protected approved-version foreign key, required | Exact immutable source version.                                                |
| `label`           | text, required, maximum 200 characters           | Minimal synthetic/approved analysis-use label.                                 |
| `input_snapshot`  | immutable structured JSON, required              | Exact canonical approved profile inputs and ERP calculation path.              |
| `input_sha256`    | lowercase SHA-256, required                      | Digest of the exact canonical `input_snapshot`.                                |
| `created_by`      | protected user foreign key, required             | Snapshot creator.                                                              |
| `approved_by`     | protected user foreign key, required             | Actor responsible for the approved source/version selection.                   |
| `approved_at`     | UTC timestamp, required                          | Approval time preserved with the snapshot.                                     |
| `created_at`      | UTC timestamp, required                          | Server-assigned snapshot creation time.                                        |
| `archived_at`     | UTC timestamp, nullable                          | Archive marker; `null` means active.                                           |

Snapshots are immutable and retained; archive is the removal path. P2.2 HAAT calculations
reference the exact snapshot and include its identity/digest in result provenance. Future
calculated estimates must preserve the same boundary.
The create action accepts only a nonblank `label` for an approved profile version; every stored
snapshot field is server-controlled and read-only.

## Canonical approval payload and digest

Approval creates `input_snapshot` with `schema_version = 1`, profile identity (`id`, `incident`,
`name`, `profile_type`, and `description`), profile-version identity (`id` and `number`), every
editable RF field listed above, and the server-controlled `erp_calculation_path`. Persisted decimal
values are represented at their declared precision, and explicit unknowns remain `null` or the
controlled `unknown` value.

`input_sha256` is the lowercase SHA-256 of UTF-8 JSON serialized with sorted keys, no insignificant
separator whitespace, and non-ASCII characters preserved. The separately named
`RFAnalysisInputSnapshot` copies the approved payload and digest; it does not recalculate or
resolve a newer profile version.

## Authorization, audit, minimization, and approval

- The backend uses `rf.view`, `rf.edit`, and `rf.approve`. Administrator, COML, and COMC role
  defaults include all three; COMT includes view/edit; Contributor and Read-only include view.
- Backend policy enforces incident membership on profile, version, approval, snapshot, and archive
  actions. Browser visibility is not authorization.
- Cross-incident profile/version/snapshot access and links are rejected.
- Approved versions and all snapshots are immutable; changes create new drafts/snapshots.
- Profile create/update/archive, version create/update/copy/approve, and snapshot create/archive
  append-only events record actor, incident, target/version, action, and changed field names. They
  do not duplicate RF values or notes.
- Digests detect changed canonical bytes; they do not provide confidentiality, source
  authentication, or RF accuracy.
- Repository fixtures, screenshots, tests, and documentation use clearly synthetic values.

Qualified COML, COMT, COMC, and RF engineering practitioners must approve every field meaning,
unit/reference, enumeration, implemented range, null/unknown behavior, cross-field rule, ERP method,
subscriber assumption, security effect, and user-facing limitation before operational suitability
is claimed.

That gate does not turn an output into a propagation study, frequency-coordination approval,
spectrum authorization, or coverage guarantee. Users remain responsible for applicable law,
licenses, coordination, agency policy, equipment behavior, terrain, structures, interference, and
field verification.
