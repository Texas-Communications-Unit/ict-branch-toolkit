# Optional terrain analysis

## Safety boundary

> **NON-PRODUCTION P3.1 TERRAIN DECISION SUPPORT**

The terrain workspace compares one source-aware sampled profile with an
earlier Phase 2 estimate. It is not a coverage guarantee, field validation,
diffraction study, frequency-coordination decision, spectrum authorization, or
regulatory study. Terrain never replaces the Phase 2 layer.

Core planning remains available when the provider is disabled, unavailable, or
unapproved.

## Default fail-closed configuration

The safe default performs no terrain retrieval:

```env
ICT_TERRAIN_PROVIDER=apps.rf_analysis.terrain.DisabledTerrainProfileProvider
ICT_TERRAIN_ENGINE=apps.rf_analysis.terrain.ProvisionalSampledLineOfSightEngine
ICT_APPROVED_TERRAIN_CONFIGURATIONS=[]
ICT_TERRAIN_MAX_DISTANCE_M=200000
ICT_TERRAIN_MAX_SAMPLES=1001
```

`GET /api/terrain-analysis-status/` should report:

- `configured: false`;
- `approved_for_analysis: false`;
- `available: false`; and
- a warning that no terrain profile provider is configured.

Do not treat a provider class name or a nonempty allowlist as approval
evidence. Record the named reviewers, date, dataset/adapter licenses, exact
commit, exact source digest, engine version, supported use, and test evidence
outside the runtime setting.

## Deterministic synthetic provider

The repository's synthetic provider is for automated tests and separately
approved synthetic evaluation only:

```env
ICT_TERRAIN_PROVIDER=apps.rf_analysis.terrain.SyntheticTerrainProfileProvider
ICT_TERRAIN_ENGINE=apps.rf_analysis.terrain.ProvisionalSampledLineOfSightEngine
ICT_SYNTHETIC_TERRAIN_MODE=flat
ICT_APPROVED_TERRAIN_CONFIGURATIONS=[{"provider":"synthetic-offline","provider_version":"terrain-profile-provider-v1","dataset_product":"ICT Toolkit deterministic terrain profile fixture","dataset_version":"synthetic-terrain-profile-v1","source_content_sha256":"125b074910d3310aec8030ae6f96f56db96809625328316c476f665daa820287","engine":"provisional_sampled_line_of_sight","engine_version":"sampled-line-of-sight-v1-provisional"}]
```

Supported fixture modes are `flat`, `ridge`, `valley`, `missing`, `boundary`,
`out_of_coverage`, `datum`, and `failure`. Changing a mode changes the provider
configuration captured in queued input evidence. It never supplies real
terrain.

## Operator workflow

1. Select an incident and confirm the status card reports the exact approved
   provider, dataset/version, source resolution, source/target vertical
   reference, engine/version, and resource limits.
2. Select one complete, approved Phase 2 coverage estimate. The linked HAAT
   record must retain antenna AMSL.
3. Enter an explicit azimuth, maximum profile distance, sample interval,
   receiver height, and clearance. Do not request an interval finer than the
   dataset resolution.
4. Queue the immutable request. Review provider, dataset, engine, application,
   parameter, Phase 2, and input-digest evidence.
5. Explicitly run it. The first implementation is synchronous; keep the
   request open until it finishes. Only queued work can be cancelled.
6. Review the Phase 2 nominal distance beside the terrain continuous-clear
   distance. Review material-difference language, first obstruction or gap,
   profile acquisition state, sample count, gap count, edge effect, warnings,
   exclusions, transformation, and result digest.
7. Use the accessible profile table to distinguish `clear`, `obstructed`,
   `missing`, and `out of coverage` states without relying on a map or color.
   Terrain history is paged and profile rows are rendered when their disclosure
   is opened.
8. Approve only if the result is complete, current, and accepted by the
   qualified reviewer. A partial or unsupported result cannot be approved.

## Failure, cancellation, and stale evidence

- Provider and internal failures expose bounded recovery messages. Technical
  exception detail belongs in protected server logs.
- Failed and cancelled records are retained. Use **Queue retry** after the
  source is restored; retry creates a new record and does not rewrite history.
- Missing samples stop the continuous-clear result. They are never
  interpolated.
- Out-of-coverage and source-resolution conditions are reported as partial or
  unsupported rather than complete.
- A provider/dataset/engine allowlist change or a changed Phase 2 result digest
  marks earlier evidence stale. Retain it and queue new work from current
  approved sources.
- Never edit result JSON, digests, job state, approval state, or provider
  identity directly in the database.

## Monitoring and audit review

Monitor bounded request duration, failure-code counts, repeated retry patterns,
database growth, result size, and provider-specific latency without logging
coordinates or profile samples. Audit events use:

- `terrain_analysis.queued`;
- `terrain_analysis.completed` or `terrain_analysis.failed`;
- `terrain_analysis.cancelled`;
- `terrain_analysis.retried`; and
- `terrain_analysis.approved`.

Audit details retain identifiers, versions, states, and digests. They must not
copy coordinates, terrain samples, RF values, provider credentials, remote
responses, or protected incident narrative.

## Real provider approval checklist

Before enabling any real local dataset or remote adapter, require documented
approval of:

- authoritative source, exact product/version/content digest, update cadence,
  resolution, horizontal/vertical references, transformation/grid, coverage,
  known gaps, uncertainty, and supported use;
- license, terms, attribution, caching, retention, redistribution, export, and
  after-action/legal-hold handling;
- whether coordinates leave the installation, endpoint allowlisting, TLS,
  authentication/secret handling, timeouts, response-size limits, parsing,
  rate limits, retries, cancellation, and failure isolation;
- compute, memory, storage, concurrency, monitoring, and backup effects;
- deterministic flat/ridge/valley, missing, boundary, out-of-coverage, datum,
  failure, cancellation, incident-isolation, and maximum-bound tests; and
- exact user-facing limits and qualified GIS/RF, security/privacy, operations,
  accessibility, legal/licensing, and maintainer sign-off.

No provider secret, token, credential, URL with embedded credentials, private
dataset, cache, or real profile belongs in the repository, frontend bundle,
test artifact, screenshot, audit detail, or GitHub discussion.

## Backup and rollback

Follow the general
[backup, restore, upgrade, and rollback runbook](backup-restore-and-rollback.md).
Migration `rf_analysis.0007_terrainanalysis` creates the retained terrain table
and indexes. Reversing it drops that evidence. Back up and verify the database
before any rollback, and never rehearse reversal on a shared or operational
database.

See [ADR-0017](../adr/0017-optional-source-aware-terrain-analysis.md) and the
[Phase 3 data model](../data-model/phase-3.md).
