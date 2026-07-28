# ADR-0015: Retained Phase 2 validation evidence bundles

## Status

Accepted for non-production prototype evaluation. Qualified RF/GIS,
security/privacy, accessibility, operations, and maintainer acceptance remains
pending.

## Context

Phase 2 produces several independently versioned records: an approved ICS 205
revision, approved RF input snapshots, source-aware elevation and HAAT,
band/environment estimates, directional estimates, field observations and
review history, and incident-local calibration. A release-candidate evaluation
must prove which exact records were compared without flattening them into an
untraceable screenshot or mutable report.

The evaluation also needs visible job state, cancellation before work starts,
error recovery, stale-evidence handling, deterministic synthetic comparison,
and a controlled export. It must not imply that a repeatable software result is
field validation, scientific model validation, frequency coordination, or
authorization.

## Decision

`Phase2ValidationBundle` is a retained, incident-scoped staged job and evidence
record.

- Queueing captures an approved plan, HAAT calculation, coverage estimate,
  directional analysis, and calibration set. The backend verifies that every
  source belongs to the incident and that the RF/HAAT/coverage/directional and
  calibration-observation links form one consistent chain.
- The input snapshot records exact source identities, versions, approvals,
  actors, timestamps, application version, and digests. Plan contact fields,
  assignment remarks, raw observation coordinates, observer/source text, and
  notes are excluded.
- Explicit `queued`, `running`, `complete`, `failed`, and `cancelled` states,
  step labels, percentage, timestamps, and minimized failure codes make work
  visible. Queue cancellation is supported. The first implementation runs
  synchronously after an explicit request and does not claim mid-request
  cancellation or background-worker durability.
- Running creates a deterministic result snapshot with supported and
  unsupported conditions, screening-only confidence, tested limits,
  sensitivity values, minimized source evidence, and measured-versus-predicted
  synthetic distance comparisons.
- Completed result evidence is immutable. Retry creates a new queued record
  linked through `supersedes`; it does not rewrite the failed or cancelled
  record.
- A completed bundle becomes stale when its own or a source digest no longer
  verifies, the elevation cache expires, the approved plan content changes, or
  linked observation/review evidence changes. Stale evidence remains visible
  but cannot be approved or exported.
- Approval fails closed unless the exact validation profile is listed in
  `ICT_APPROVED_PHASE2_VALIDATION_PROFILES`. This separate gate requires
  qualified RF/GIS, security/privacy, and maintainer acceptance.
- Controlled deterministic JSON export requires both `rf.approve` and
  `plan.export`. Every exact export byte stream is SHA-256 recorded in the
  append-only audit chain, and an authorized user can verify a downloaded
  digest against that audit event.

## Consequences

The evidence preserves the historical decision chain and can be reproduced
without silently using newer sources. It also preserves failed, cancelled, and
stale history.

The synchronous execution model is intentionally modest. A later background
worker requires a separate design for leasing, idempotency, cooperative
cancellation, recovery, monitoring, and secret/data boundaries. The current
plan model also lacks a direct assignment-to-RF-profile relationship, so the
bundle records this as an unsupported traceability condition instead of
inventing a link.

No bundle is an operational approval, propagation study, coverage guarantee,
coordination result, or spectrum authorization.
