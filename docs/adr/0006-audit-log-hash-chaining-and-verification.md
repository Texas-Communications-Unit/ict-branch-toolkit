# ADR-0006: Audit log hash chaining and self-service export digest verification

- Status: Accepted for P1.5
- Date: 2026-07-24
- Decision owners: Maintainers

## Context

ADR-0005 recorded a SHA-256 digest on every export's audit event but left two items explicitly
out of scope, and issue #6 (P1.5) remained open to track them: audit events were append-only only
at the application layer, with no defense against a database administrator directly editing a
row; and there was no self-service way to verify a downloaded file's digest, only a documented
manual procedure requiring `audit.view` (administrator-only).

## Decision

`AuditEvent` now carries a monotonically increasing `sequence`, a `previous_hash`, and a
`record_hash`. `record_hash` is the SHA-256 of the canonical JSON of `{previous_hash, sequence,
actor_id, action, target_type, target_id, details}`; the first event chains from a fixed
64-character genesis hash of zeroes. `apps.audit.services.record_event()` computes the chain
under `transaction.atomic()` with `select_for_update()` on the latest-sequence row so concurrent
writers cannot both claim the same `sequence`. `verify_audit_chain()` walks the whole table in
sequence order, recomputing each hash and confirming `previous_hash` linkage, and returns the
first broken event if any. `occurred_at` is intentionally excluded from the hashed payload because
it is assigned by the database on save and is not known before the hash must be computed;
`sequence` (assigned by the application, before save) guarantees ordering instead.

A new `POST /api/audit/revisions/<revision_id>/exports/<format>/verify/` endpoint
(`apps.audit.views.ExportDigestVerificationView`) accepts either a `content_sha256` hex digest or
an uploaded file (hashed server-side) and reports whether it matches a recorded export audit
event for that revision and format. It requires the same permission that produced the export
(`plan.export` for `pdf`, `site.export` for `map`/`kml`/`geojson`/`csv`) rather than `audit.view`,
so verification is available to the same operators who could export, not administrators only.

## Consequences

- A database administrator (or anyone with direct write access) editing, reordering, or deleting a
  past audit row now breaks the hash chain, detectable by `verify_audit_chain()`. This closes the
  gap ADR-0005 explicitly left open, without weakening the existing append-only application-layer
  guard.
- Existing `AuditEvent` rows are backfilled by a data migration (`0002_audit_event_hash_chain`)
  that assigns `sequence`/`previous_hash`/`record_hash` in `(occurred_at, id)` order before the
  columns are tightened to non-null/unique. The migration duplicates the hashing logic inline
  rather than importing `apps.audit.services`, per Django's guidance that migrations should not
  depend on application code that can change later.
- Operators can now self-verify a downloaded export without administrator involvement, replacing
  the fully manual procedure in `docs/operations/export-verification.md`. Chain verification
  itself (`verify_audit_chain()`) has no HTTP endpoint yet; it is intended for a management command
  or administrator tooling, not a self-service check, since a broken chain is a
  system-integrity concern rather than a routine operator task.
- The chain proves no *past* record was altered after being written; it cannot prevent an attacker
  with database write access from truncating the table and starting a new chain from the genesis
  hash. Detecting that requires comparing sequence continuity against an independent record (e.g.
  offline backups) and remains an operational control, not something this decision solves.

## Alternatives considered

Requiring `audit.view` for the verification endpoint, matching the existing manual procedure, was
rejected because it defeats the point of a *self-service* check — the roles that can produce an
export (COML, COMC, Administrator) are not always the roles with `audit.view`. Signing each record
with an asymmetric key instead of hash chaining was considered but deferred as unnecessary
complexity for the prototype; hash chaining alone is sufficient to detect tampering with existing
rows, which was the concrete gap being closed.
