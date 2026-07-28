# ADR-0012: Field observations and incident-local calibration

- Status: Accepted for synthetic prototype evaluation
- Date: 2026-07-28
- Issue: #19

## Context

Calculated range estimates remain provisional until compared with structured field evidence.
Uncontrolled notes, mutable observations, exact coordinates, and opaque curve fitting would make
that comparison difficult to review and could expose sensitive incident or infrastructure data.
A fitted result must not silently become an organization default or imply coverage, coordination,
or operational authority.

## Decision

The Toolkit records each field observation as an immutable incident-scoped record tied to two
approved RF input snapshots and, when applicable, an approved coverage estimate or directional
analysis. The record distinguishes measured, operator, imported, and modeled evidence; captures a
bounded time window, classification, collection/source fields, environment, measurements, quality
flags, and source revision; and retains a canonical input digest.

Location handling is selected before persistence:

- `exact` retains validated WGS 84 coordinates and the declared precision;
- `generalized` rounds coordinates to the declared grid before model creation, snapshots, audit,
  or response serialization; and
- `redacted` discards supplied coordinates before model creation and retains no coordinate or
  precision value.

Corrections create a new observation with `supersedes`. Review decisions are separate immutable,
append-only approval or exclusion records chained by evidence digest. A superseded observation
cannot be newly approved.

Calibration sets are immutable, named, incident-scoped versions. The provisional
`observation-envelope-v1-provisional` method:

1. requires currently approved, non-superseded observations;
2. fits only records containing positive measured and predicted distances;
3. exposes missing pairs and ratios outside the declared bounds as exclusions;
4. uses the median bounded measured-to-predicted ratio as an incident-local distance multiplier;
5. records deterministic before/after error measures, parameters, inputs, warnings, exclusions,
   recommendation, and digests; and
6. marks the recommendation `not_promoted` and
   `organization_default_overwritten = false`.

Draft calculation is permitted for synthetic evaluation. Approval fails closed unless the exact
algorithm version appears in the server-side `ICT_APPROVED_CALIBRATION_METHODS` allowlist and every
included observation still matches its captured input and review evidence.

## Consequences

- Exact and generalized coordinates, observer/source text, and notes remain sensitive application
  records. Audit events contain only action, field names, record IDs, and digests.
- Generalization protects the stored copy but cannot undo disclosure that occurred before the
  browser submitted a coordinate. Operators should select redaction when the application must not
  retain a location.
- Append-only decisions preserve review history and make later exclusion visible.
- The initial method is deliberately small, deterministic, and explainable. It is not a
  propagation model, scientific validation study, frequency-coordination decision, coverage
  guarantee, or organization-wide preset.
- Non-synthetic collection and calibrated-preset approval remain behind security/privacy,
  incident-authority, and qualified RF review.

## Rejected alternatives

- Updating an observation in place was rejected because it would erase correction history.
- Storing exact coordinates and masking them only in the interface was rejected because the
  sensitive value would still exist in the database and backups.
- Fitting every selected record was rejected because missing and extreme values must remain
  explicit rather than silently biasing the result.
- Automatically replacing a configured coverage preset was rejected because local evidence is
  incident-specific and requires separate human acceptance.
