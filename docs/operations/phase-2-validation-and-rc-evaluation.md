# Phase 2 validation and release-candidate evaluation

## Safety boundary

> **NON-PRODUCTION PHASE 2 VALIDATION EVIDENCE — SYNTHETIC DATA ONLY**

The P2.6 workflow checks deterministic software behavior, source provenance,
permissions, stale-data behavior, and operational recovery. It does not
validate RF propagation accuracy and does not authorize deployment, real
incident data, a frequency, a communications plan, or a production release.

Each bundle is limited to 1,000 plan assignments and 1,000 calibration
observations, and file-based digest verification is limited to 10 MiB. These
are provisional resource-safety guards, not tested operational capacity.

## Approval gate

The safe default is:

```env
ICT_APPROVED_PHASE2_VALIDATION_PROFILES=[]
```

That setting allows authorized users to queue, run, inspect, cancel, and retry
synthetic draft evidence, but prevents approval and controlled export. After
qualified RF/GIS, security/privacy, accessibility, operations, and maintainer
review accepts this exact implementation, a protected evaluation environment
may use:

```env
ICT_APPROVED_PHASE2_VALIDATION_PROFILES=["phase-2-validation-v1-provisional"]
```

The allowlist authorizes only the exact profile version for controlled
release-candidate evidence. It does not approve the underlying models for
operational use or permit non-synthetic data.

The Phase 2 milestone gate was accepted by Eric M. Gildersleeve on July 28,
2026, for synthetic non-production evaluation with the documented
best-estimate limitations. That acceptance does not change the fail-closed
default, make profile enablement automatic, or authorize official coverage
mapping, RF-penetration claims, or non-synthetic data. Any environment that
enables the provisional profile must record that separate deployment-specific
configuration decision.

## Prepare an evidence bundle

1. Select one incident.
2. Confirm an ICS 205 revision is approved and locked.
3. Confirm the HAAT, coverage, directional, and calibration records are
   approved and complete.
4. Confirm the coverage and directional records use the selected HAAT and its
   infrastructure RF snapshot.
5. Confirm every calibration observation uses the selected infrastructure and
   subscriber RF pair and its latest review remains approved.
6. Queue the bundle. Review the captured input digest and source identities.
7. Explicitly run it. Keep the browser open until the synchronous request
   finishes. Queue cancellation is available before execution; mid-request
   cancellation is not.
8. Review confidence, supported/unsupported conditions, tested limits,
   sensitivity, deterministic comparisons, exclusions, warnings, and all
   digests.
9. If it fails or is cancelled, preserve that record and queue a retry. If it
   is stale, select current approved sources and create a new bundle.
10. A qualified reviewer may approve only after the server gate is explicitly
    enabled.

## Controlled export and verification

Approved, current evidence can be exported only by a user with both
`rf.approve` and `plan.export`. The JSON is deterministic for the approved
record. The response includes `X-Content-SHA256`, and the append-only audit
event stores the same digest and byte size without copying RF values,
coordinates, contacts, notes, or credentials.

Use the interface verification form or:

```sh
sha256sum phase-2-validation-<bundle-id>.json
```

Submit the resulting 64-character digest to:

```text
POST /api/phase2-validation-bundles/<bundle-id>/verify/
```

Verification proves only that identical bytes were previously exported from
that bundle and recorded in this installation's audit chain. It does not
authenticate an external source or establish RF correctness.

## Stale and failed evidence

Approval and export are blocked when:

- bundle input or result bytes no longer match their digest;
- plan, HAAT, coverage, directional, or calibration evidence no longer matches
  its retained digest;
- the selected elevation snapshot is stale;
- a calibration observation is superseded; or
- the latest observation review or evidence digest differs from the approved
  calibration membership.

Do not delete or rewrite the old record. Preserve it for audit history, correct
or reapprove the underlying source through its normal immutable lifecycle, and
queue a new bundle.

Failure responses expose a bounded code and recovery instruction. Detailed
exception information belongs in protected server logs, not API responses or
audit details.

## Release-candidate evidence

The `Phase 2 RC evaluation` workflow uses Node.js 24 GitHub Actions, builds a
clean production Compose stack, checks PostgreSQL/PostGIS health, runs the
synthetic P2.6 integration suite inside the installed backend image, verifies
backup and isolated restore, rehearses the P2.6 migration rollback/reapply, and
uploads sanitized evidence.

Normal CI and Security workflows remain required for:

- backend/PostgreSQL tests, migration drift, OpenAPI, frontend format/lint/type/
  tests/build, browser and WCAG automation, and container builds;
- dependency audit, Gitleaks, CodeQL, Trivy, and CycloneDX SBOM evidence.

RF/GIS limitation, security/privacy, operations, automated accessibility, and
exact-commit maintainer acceptance for the Phase 2 milestone are recorded in
the [candidate evidence](../releases/v0.2.0-rc.1-evidence.md). Manual keyboard,
zoom/reflow, contrast, and screen-reader evaluation remains tracked in Issue
#69, and no formal accessibility-conformance claim is made. Publishing the
candidate does not make it deployable for production or authorize
non-synthetic data.

## Recovery and rollback

Use the general
[backup, restore, upgrade, and rollback runbook](backup-restore-and-rollback.md).
Migration `rf_analysis.0006_phase2validationbundle` creates only the new
evidence table and indexes. Before any rollback, preserve approved evidence
through the database backup process; reversing the migration drops that table.
Never rehearse migration reversal on a shared or operational database.
