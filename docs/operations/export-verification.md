# Verifying an official export

Official ICS-205 exports (PDF, GeoJSON, CSV, KML, and the SVG map) are only ever generated from an
approved, locked plan revision. Each export visibly states:

- Approval status (`APPROVED`)
- The approved revision's `approved_at` timestamp
- The application version that produced it (`app_version` / footer text)

## Confirming a downloaded file matches what the server actually exported

Every export is recorded as an audit event (`plan_revision.pdf_exported` or
`site_export.<format>`) containing a SHA-256 digest (`content_sha256`) of the exact bytes returned
to the requester, the byte size, and the source revision's number and status. An administrator
with `audit.view` permission can look up the matching audit event and compare its
`content_sha256` against a digest computed from the file in hand, for example:

```
certutil -hashfile ics-205-revision-3.pdf SHA256   # Windows
shasum -a 256 ics-205-revision-3.pdf               # macOS/Linux
```

If the digests do not match, the file is not the one the server generated for that audit event —
treat it as unverified and re-export from the toolkit rather than relying on it operationally.

## Limitations

- This is a manual comparison today. There is no self-service "upload and verify" endpoint yet.
- The digest proves what left the server at export time. It cannot prove that a copy was not
  further edited after an operator already verified it once — verification must be repeated on the
  copy actually being relied upon.
- Audit events are append-only at the application layer but are not cryptographically chained.
  Direct database administrator access could still alter a recorded digest; treat the audit log's
  integrity as bounded by normal database access controls.
- Exports are deterministic per approved revision (identical bytes every time), so the digest
  recorded for the *first* export of a revision will match every later export of that same
  revision — a matching digest across two files does not by itself prove which export request
  produced the copy you have, only that its content is unaltered.
