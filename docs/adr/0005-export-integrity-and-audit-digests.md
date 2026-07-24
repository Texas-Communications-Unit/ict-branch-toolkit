# ADR-0005: Export integrity stamping and audit digests

- Status: Accepted for P1.5
- Date: 2026-07-24
- Decision owners: Maintainers

## Context

Issue #6 (P1.5) requires that official ICS-205 exports (PDF, GeoJSON, CSV, KML, SVG map) can only be
produced from an approved, locked revision; that each export visibly states its approval state,
app version, and source revision; and that every export is recorded with enough information to
detect later tampering with a downloaded file. ADR-0003 and ADR-0004 already require the PDF and
spatial exports to be deterministic so that repeated exports of the same approved revision are
byte-identical. Any change here must not break that determinism guarantee, since operators and CI
rely on it to prove an export was not silently altered between two generations.

## Decision

Every export continues to require an approved revision: `render_ics205` raises unless
`revision.is_locked`, and `approved_site_records` raises unless `revision.status == APPROVED`.
Both are unchanged by this decision — this ADR only adds stamping and a recorded digest on top of
that existing gate.

Exports now stamp their approval state, the revision's immutable `approved_at` timestamp, and the
running `settings.APP_VERSION` directly in the output (PDF footer text, GeoJSON top-level fields,
CSV columns, KML description, SVG caption). We deliberately use `revision.approved_at` — fixed at
approval time — rather than the wall-clock time of the individual export request, so exports of the
same approved revision remain byte-for-byte identical no matter when or how many times they are
generated. The real per-request export time is still captured, in the audit event described below,
so "when was this specific file produced" remains answerable without weakening determinism.

`apps.audit.services.record_export()` wraps the existing append-only `record_event()` to log, for
every export: the actor, the source revision (as `target`), the export format, a SHA-256 digest of
the exact bytes returned to the requester, the byte size, and the revision's number and status at
export time. `occurred_at` on the audit event is the append-only, server-assigned generation
timestamp for that specific export. `PlanRevisionViewSet.pdf` and `SpatialExportView.get` both now
call `record_export()` instead of a bare `record_event()`.

## Consequences

- Operators can verify a previously downloaded file by re-computing its SHA-256 digest and
  comparing it against the `content_sha256` recorded on the matching audit event; a mismatch means
  the file was altered, corrupted, or is not the file that was actually exported. This is a manual
  comparison today — there is no dedicated verification endpoint yet.
- Because approval freezes assignment and site-link snapshots (ADR-0003, ADR-0004) and revisions are
  immutable once approved, re-exporting an approved revision after a later draft copy or edit
  produces the same bytes and therefore the same digest — concurrent drafting activity cannot
  silently change what an already-approved export represents.
- The recorded digest only proves what left the server at export time. It cannot prove a
  downstream party did not further edit a file after checking it — that remains an operator
  process control, documented in `docs/operations/export-verification.md`.
- Audit events remain append-only and are not themselves cryptographically chained; a database
  administrator with direct write access to the audit table could still alter a recorded digest.
  This is an accepted limitation for the prototype; a tamper-evident log (e.g. hash chaining) is
  out of scope for this decision.

## Alternatives considered

Embedding the wall-clock export time into the file bytes was rejected because it would make
otherwise-identical exports non-deterministic, breaking the ADR-0003/ADR-0004 guarantee and the
existing byte-equality tests. A dedicated "verify this file" upload endpoint was deferred; the
audit log already carries the digest needed for manual verification, and an endpoint can be added
later without changing this decision.
