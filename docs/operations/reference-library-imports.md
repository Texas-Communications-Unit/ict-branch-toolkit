# Reference library import operations

Only administrators may validate or apply channel-library imports. Imports are JSON, atomic, source-versioned, and additive. An existing release cannot be replaced. Dry runs write nothing and return structured field paths, codes, and messages.

## CISA release selection

At import time, an administrator must visit the official [CISA Field Operations Guides page](https://www.cisa.gov/resources-tools/resources/field-operations-guides), identify the latest applicable release, download it from a `cisa.gov` source, retain the source URL and release/version, calculate its SHA-256 digest, and document permitted use. Do not infer the current version from an older plan or previously imported release.

As of July 22, 2026, the latest official CISA material located during P1.1 review identifies **NIFOG version 2.02**. That observation is not a permanent application default; recheck CISA before every proposed import. Historical releases remain available because approved or published plans must retain the release they referenced.

## Human approval gate

Dry-run validation is allowed before approval. Applying any `cisa_*` source requires an exact object in `ICT_APPROVED_REFERENCE_IMPORTS`:

```json
[
  {
    "source_type": "cisa_nifog",
    "version": "<approved version>",
    "authoritative_url": "<exact approved cisa.gov URL>",
    "content_sha256": "<lowercase SHA-256>"
  }
]
```

Approval must record the reviewing maintainer, qualified communications reviewer, source, version, URL, digest, permitted use, transformation method, validation results, and decision date outside the environment variable. A newer release creates a new source release; it never rewrites old records.

## Import procedure

1. Back up and test restoration of the application database.
2. Convert only the approved source fields. Keep conventional channels and trunked talkgroups separate and express frequencies as integer hertz.
3. Submit with `dry_run: true`; resolve every structured error and review counts.
4. Compare a sample against the authoritative source with a qualified reviewer.
5. Configure the exact approval object and restart the backend through the controlled deployment process.
6. Submit the unchanged payload with `dry_run: false`.
7. Verify the release, counts, provenance, payload digest, and audit event.
8. Remove or retain the approval configuration according to local change-control policy. Removing it does not remove the imported historical release.

If persistence fails, the database transaction rolls back the source, release, channels, talkgroups, import record, and audit event together. Do not delete an imported release to correct it; fix the source data and import a newly identified version.

## Other CISA guides

- **AUXFOG:** relevant as an optional training and auxiliary-communications reference. Review its current official version and permitted use separately; do not merge its records into NIFOG provenance.
- **State or regional electronic FOGs:** potentially useful for an installation serving that jurisdiction, but may contain local restrictions or non-public operational details. Require source-owner permission and a separate source/release record before import.
- **Planning, governance, broadband, exercise, and interoperability-continuum guides:** useful documentation, but not channel-library sources and therefore should be linked as references rather than imported as frequency or talkgroup records.
