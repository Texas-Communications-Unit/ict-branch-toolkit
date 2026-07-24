# Verifying an official export

Official ICS-205 exports (PDF, GeoJSON, CSV, KML, and the SVG map) are only ever generated from an
approved, locked plan revision. Each export visibly states:

- Approval status (`APPROVED`)
- The approved revision's `approved_at` timestamp
- The application version that produced it (`app_version` / footer text)

## Confirming a downloaded file matches what the server actually exported

Every export is recorded as an audit event (`plan_revision.pdf_exported` or
`site_export.<format>`) containing a SHA-256 digest (`content_sha256`) of the exact bytes returned
to the requester, the byte size, and the source revision's number and status.

### Self-service verification endpoint

`POST /api/audit/revisions/<revision_id>/exports/<format>/verify/` (`format` is `pdf`, `map`,
`kml`, `geojson`, or `csv`) checks a file against the recorded digest without administrator
involvement. It requires the same permission that produced the export (`plan.export` for PDFs,
`site.export` for spatial formats), so any operator who could export the revision can also verify
it. Send either a precomputed digest:

```
POST /api/audit/revisions/<revision_id>/exports/pdf/verify/
Content-Type: application/json
Authorization: Token <token>

{"content_sha256": "<sha256 hex digest of the file>"}
```

or the file itself as multipart form data under the `file` field, and the server hashes it. The
response is `{"verified": true, ...}` with the matching audit event's metadata, or
`{"verified": false, "detail": "..."}` when no export audit event matches that digest for the
given revision and format.

### Manual comparison

An administrator with `audit.view` permission can also look up the matching audit event directly
and compare its `content_sha256` against a digest computed from the file in hand, for example:

```
certutil -hashfile ics-205-revision-3.pdf SHA256   # Windows
shasum -a 256 ics-205-revision-3.pdf               # macOS/Linux
```

If the digests do not match, the file is not the one the server generated for that audit event —
treat it as unverified and re-export from the toolkit rather than relying on it operationally.

## Limitations

- The digest proves what left the server at export time. It cannot prove that a copy was not
  further edited after an operator already verified it once — verification must be repeated on the
  copy actually being relied upon.
- Audit events are hash-chained (each record's hash covers the previous record's hash), so
  retroactively editing, deleting, or reordering a past event — even via direct database access —
  breaks the chain and is detectable by recomputing it (`apps.audit.services.verify_audit_chain`).
  There is no scheduled or automatic chain-verification job yet; running it today requires a
  Django shell or a future management command.
- Exports are deterministic per approved revision (identical bytes every time), so the digest
  recorded for the *first* export of a revision will match every later export of that same
  revision — a matching digest across two files does not by itself prove which export request
  produced the copy you have, only that its content is unaltered.
