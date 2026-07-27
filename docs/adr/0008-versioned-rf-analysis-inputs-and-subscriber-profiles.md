# ADR-0008: Versioned RF analysis inputs and subscriber profiles

- Status: Accepted for P2.1 prototype implementation; operational approval pending
- Date: 2026-07-27
- Decision owners: Project maintainers with qualified COML, COMT, COMC, and RF engineering reviewers

## Context

Phase 2 adds controlled radio-frequency (RF) inputs for later calculated planning estimates. Those
inputs must not live as mutable installation settings, undocumented browser constants, or hidden
subscriber defaults. The application must preserve the transmitter, receiver, antenna, feed-line,
gain, loss, polarization, band, emission, mounting, and site-height values used by an analysis.
P2.1 builds on the P1.6 centralized authorization and append-only audit controls.

Transmitter output power and effective radiated power (ERP) are not interchangeable. The
[FCC definition](https://docs.fcc.gov/public/attachments/DOC-396579A1.pdf) describes ERP as antenna
input power multiplied by antenna power gain and distinguishes effective isotropic radiated power
(EIRP) by its isotropic gain reference. P2.1 uses that distinction to normalize an entered `dBi`
or `dBd` antenna gain before calculating ERP. The application preserves the transmitter power,
losses, antenna gain and reference, conversion convention, intermediate antenna-input power,
formula version, and result.

Antenna center height above ground level (AGL), antenna center height above mean sea level (AMSL),
and height above average terrain (HAAT) also have different references. They cannot be aliases or
automatic substitutes for one another.

Only synthetic or explicitly approved data may be used. All numerical ranges, enumerations,
cross-field rules, conversion conventions, and subscriber assumptions are provisional. **No
operational default is approved.** Qualified COML, COMT, COMC, and RF engineering practitioners
must complete the Issue #15 human gate before the fields or profiles are treated as operationally
suitable.

## Decision

### Implemented aggregates

P2.1 implements only these aggregates:

- `SubscriberProfile`: an incident-scoped stable identity categorized as `portable`, `mobile`,
  `fixed`, or `configurable`;
- `SubscriberProfileVersion`: numbered draft or immutable approved RF values for one profile; and
- `RFAnalysisInputSnapshot`: a named, incident-scoped immutable copy of one approved profile
  version for later analysis use.

These three records are the complete P2.1 aggregate boundary. A future analysis/result model must
reference the exact `RFAnalysisInputSnapshot` it used; that linkage requires its own implementation
and review.

Profiles and snapshots are archived rather than deleted. Approved profile versions and snapshots
are immutable. Changes copy an approved profile version into a new numbered draft.

### Canonical quantities and explicit unknowns

Use typed fields and canonical quantities:

- frequency and emission bandwidth in integer hertz (`Hz`);
- transmitter power and ERP in watts (`W`);
- feed-line length, AGL, AMSL, and HAAT in meters (`m`);
- receiver sensitivity in `dBm`, retaining its one-milliwatt reference; and
- gain and loss as power-like logarithmic ratios in `dB`, with antenna gain reference recorded as
  `dbi`, `dbd`, or `unknown`.

[NIST SP 811 Chapter 4](https://www.nist.gov/pml/special-publication-811/nist-guide-si-chapter-4-two-classes-si-units-and-si-prefixes)
identifies hertz, watt, and meter within the SI system.
[NIST SP 811 Chapter 5](https://www.nist.gov/pml/special-publication-811/nist-guide-si-chapter-5-units-outside-si)
requires the reference quantity for logarithmic quantities to be specified and uses
`10^(dB/10)` for power-like ratios.

Nullable numeric values and nullable version text use `null` for explicitly unknown. The profile
description uses blank for not provided. Controlled fields use the explicit `unknown` choice where
one exists. No unknown representation means zero or authorizes a service or browser to inject a
value. Zero is retained as a real value only where the field and provisional validation rules
allow it.

### Facts and assumptions

Every `SubscriberProfileVersion` has one version-level `input_basis`:

- `unknown`;
- `recorded_fact`;
- `modeled_assumption`; or
- `mixed`.

The existing `notes` field records non-sensitive source/method context and explains which field
groups are facts versus assumptions. Nonblank notes are required when `input_basis` is `mixed`.
P2.1 does not claim per-field provenance. Adding it would require a later migration, API, threat,
and usability decision.

Notes must not contain credentials, personal contacts, protected channel details, private
infrastructure information, equipment serial numbers, or unrelated incident narrative.

### ERP calculation and preservation

`erp_source` is `unknown`, `entered`, or `calculated`.

- `unknown` means ERP has not been established.
- `entered` preserves a reviewed ERP value without pretending the application derived it and
  requires nonblank notes identifying the non-sensitive source/method.
- `calculated` requires a complete transmitter-power, system-loss, antenna-gain, and gain-reference
  path. The server writes `effective_radiated_power_w` and `erp_calculation_path`.

The versioned prototype method is:

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

The `2.15 dB` dBi-to-dBd offset is a **provisional prototype conversion convention pending
qualified review**, not an FCC operational default. For calculated ERP, `erp_calculation_path`
preserves method version `erp-v1-provisional`, the formula, exact transmitter/loss/gain inputs,
original gain reference, applied offset, normalized dBd gain, total loss, antenna-input power, net
gain, and calculated ERP.
Missing or unknown required values cause the calculated-ERP request to be rejected with the
missing field names; they are not persisted as unknown ERP. The application does not assume zero
loss, a gain reference, or an equipment default.

### Height references

Store these separately:

- `antenna_center_agl_m`: antenna-center distance above the local ground reference;
- `antenna_center_amsl_m`: antenna-center elevation above mean sea level; and
- `haat_m`: height relative to average terrain under a separately documented method.

The implementation does not derive one from another. AGL/AMSL consistency checks and any future
HAAT calculation require an approved terrain/elevation source, method, tolerance, and method
version. Until then, all three are independently entered or explicitly unknown.

### Approval snapshots and digests

Approving a `SubscriberProfileVersion` freezes its canonical `input_snapshot` and
`input_sha256`, ERP calculation path, actor, and approval time. The SHA-256 digest identifies the
canonical snapshot bytes; it is not encryption, source authentication, or proof of RF accuracy.
The version 1 payload includes profile and profile-version identity, every editable RF field, and
the server-controlled calculation path. Its digest is calculated from sorted-key, compact UTF-8
JSON so the same canonical payload has the same digest.

Creating an `RFAnalysisInputSnapshot` copies one approved version's canonical input snapshot and
digest into a separately named, incident-scoped immutable record with creator, approver, approval
time, creation time, and archival marker. It cannot point across incidents.

A later approved analysis must reference this exact snapshot rather than resolving a current
profile version. That future relationship is not implemented by P2.1 and must not be implied by
snapshot creation alone.

### Authorization, audit, and data minimization

Backend policy enforces incident membership for profile, version, approval, snapshot, and archive
actions. Hiding a browser control is not authorization.

Material actions create append-only audit events containing actor, incident, aggregate/version
identifiers, action, changed field names, and snapshot digest where applicable. Audit details do
not duplicate RF values or notes.

The model stores generic labels and configuration needed for analysis, not serial numbers, asset
owners, personal contacts, credentials, protected channel details, or private infrastructure
identifiers. Repository fixtures, screenshots, tests, and documentation remain synthetic.

## Consequences

- P2.1 provides migrations, API/OpenAPI, incident-scoped permissions, tests, and an authenticated
  browser workflow for controlled subscriber profiles, versions, approvals, and snapshots.
- Exact profile versions and digest-bound snapshots prevent later edits from rewriting prior
  analysis inputs.
- Explicit unknowns reduce false precision but intentionally leave some ERP values incomplete.
- Version-level `input_basis` distinguishes facts from assumptions coarsely; mixed versions rely on
  disciplined notes because per-field provenance is not implemented.
- Separate AGL, AMSL, and HAAT fields prevent convenient but incorrect substitution.
- The implemented defensive validation ranges limit malformed input but remain provisional and
  are not approved equipment capabilities, model applicability limits, or operational defaults.
- Snapshot approval and calculation do not establish propagation accuracy, frequency coordination,
  spectrum authorization, or a coverage guarantee.

## Alternatives considered

- **Unversioned installation settings or browser constants:** rejected because later changes would
  rewrite the meaning of prior results and hide assumptions.
- **Store only ERP:** rejected because it conflates transmitter output, system losses, antenna
  input power, antenna gain reference, and derived radiated power.
- **One generic antenna-height field:** rejected because AGL, AMSL, and HAAT have different
  references and uses.
- **Required numeric defaults or automatic profile selection:** rejected because plausible
  defaults create false precision and no operational defaults are approved.
- **Per-field provenance objects:** deferred. The implemented contract uses version-level
  `input_basis` plus `notes`.
