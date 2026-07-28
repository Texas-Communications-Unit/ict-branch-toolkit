# Phase 3 advanced-operations data model

## Scope and safety

P3.1 adds one retained `TerrainAnalysis` aggregate for optional, directional
terrain comparison. It references an existing complete, approved Phase 2
`CoverageEstimate`, its radio site, and its linked HAAT evidence. It does not
modify the site, HAAT calculation, coverage estimate, ICS 205, or map layer.

Only synthetic or explicitly approved data is allowed. All provider,
resolution, transformation, algorithm, parameter, material-difference, and
resource-limit choices are provisional. See
[ADR-0017](../adr/0017-optional-source-aware-terrain-analysis.md).

## `TerrainAnalysis`

| Field group           | Retained evidence                                                                                                                                                                                                                  |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Scope and lineage     | UUID, incident, site, Phase 2 coverage estimate, optional failed/cancelled `supersedes` record                                                                                                                                     |
| Source identity       | provider/version, dataset product/version; the full input snapshot also records horizontal/vertical/target reference, resolution, terms, permitted use, coverage, content digest, offline/network mode, and provider configuration |
| Method identity       | engine/version and application version; the input/result snapshots retain capability, method, parameters, tested limits, supported/unsupported conditions, and disclaimer                                                          |
| Requested parameters  | azimuth degrees, maximum distance meters, sample interval meters, receiver height meters, clearance meters                                                                                                                         |
| Staged lifecycle      | `queued`, `running`, `complete`, `failed`, or `cancelled`; step, percentage, bounded failure code/message, start/completion/update timestamps                                                                                      |
| Result classification | blank until run, then `complete`, `partial`, or `unsupported`                                                                                                                                                                      |
| Review lifecycle      | `draft` or `approved`, creating/approving actors and timestamps                                                                                                                                                                    |
| Integrity             | canonical input/result JSON snapshots and lowercase SHA-256 digests                                                                                                                                                                |

The canonical input snapshot also retains:

- exact site identifier and WGS 84 coordinate;
- exact Phase 2 result digest, engine/version, and
  conservative/nominal/optimistic distances;
- exact HAAT identifier, result digest, and antenna AMSL; and
- source descriptor, provider configuration, engine description, versioned
  EPSG:4326 path-generation method/mean-Earth radius/rounding, and request
  parameters.

The result snapshot retains:

- schema/classification/application/input digest;
- dataset identity, retrieval time, transformation, and acquisition state;
- algorithm identity, capabilities, parameters, and tested limits;
- every requested sample's distance, azimuth, WGS 84 location, source and
  transformed elevation, acquisition state, and reason;
- for supported complete samples, curvature adjustment, receiver and
  obstruction slopes, and visible/obstructed decision;
- sample, complete, and gap counts; source edge state; sample digest;
- continuous clear distance, first obstruction/gap, obstruction count,
  receiver height, clearance, and effective-Earth-radius factor;
- Phase 2 and terrain distances, difference, percentage, material threshold,
  material-difference state, explanation, and explicit separate-layer rule;
  and
- supported/unsupported conditions, warnings, exclusions, explanation, and
  disclaimer.

Coordinates and profiles are protected incident evidence. Audit events retain
only identifiers, versions, lifecycle states, counts where applicable, and
digests; they do not copy the input/result snapshots.

## Lifecycle rules

- Queueing requires a complete, approved Phase 2 estimate whose linked HAAT
  record retains antenna AMSL.
- Provider and engine selection are server-controlled. Queueing fails closed
  unless the exact source and engine match the configured approval object.
- Requested distance cannot exceed `ICT_TERRAIN_MAX_DISTANCE_M`; the derived
  sample count cannot exceed `ICT_TERRAIN_MAX_SAMPLES`.
- Queueing creates the canonical input snapshot and digest. Inputs are
  immutable afterward.
- Only a queued record can run or be cancelled. The first run is synchronous.
- Completion creates immutable result evidence. Expected provider failure and
  internal failure preserve a bounded failure state without exposing exception
  detail.
- Only failed or cancelled work can be retried. Retry creates a new record
  linked by `supersedes`.
- Only a current `complete` result can be approved. Partial, unsupported,
  failed, cancelled, and stale records remain retained and visible.
- Provider/dataset/engine identity or Phase 2 digest changes mark completed
  evidence stale; no automatic recalculation occurs.
- Hard deletion is rejected. Database backup/retention procedures govern
  preserved records.

## API and authorization

- `GET /api/terrain-analysis-status/` exposes capability, exact configured
  source/method identity, approval/availability, limits, and disclaimers.
- `GET /api/terrain-analyses/?incident=<uuid>` and detail retrieval require
  `rf.view` within the incident.
- Creation, run, queued cancellation, and retry require incident `rf.edit`.
- Approval requires incident `rf.approve`.

Browser visibility is not the authorization boundary; the backend scopes every
record to authorized incident memberships.

## P3.2 offline continuity aggregates

P3.2 adds three retained server aggregates. The encrypted browser envelope is
device-local and is not a fourth server record.

### `OfflinePackage`

| Field group       | Retained evidence                                                                                                                     |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Identity/scope    | UUID, incident, requesting actor, device UUID, explicit revision/release/site/terrain/attachment selections, and vector-map selection |
| Manifest          | schema version, selected counts/IDs, package byte size, payload digest, classification, revision-state digests, and manifest SHA-256  |
| Protected payload | exact selected incident/revision/library/site/terrain snapshot; cleared by controlled purge while the manifest and receipts remain    |
| Chain state       | last accepted sequence and mutation digest                                                                                            |
| Lifecycle         | `active`, `locked`, `expired`, `revoked`, or `purged`; expiration and lock/revocation/purge timestamps                                |

The package cannot be hard-deleted through the model. Expiration and revocation
block synchronization. Purge clears payload and mutable revision state but
retains the manifest digest and chain evidence.

### `OfflineMutationReceipt`

Each append-only receipt uses the client mutation UUID as its primary key and
retains package, sequence, actor/device snapshots, supported operation,
object/revision IDs, previous/payload/mutation hashes, payload snapshot, base
timestamp, client occurrence time, server receipt time, disposition, and
bounded result.

The server checks package scope, current permission, device/actor identity,
sequence, previous hash, canonical payload and mutation digests, revision
status/digest, and object timestamp before applying content. An exact retry
returns `duplicate` without creating another receipt. A reused UUID with
different content is rejected.

### `OfflineConflictResolution`

One append-only resolution may be linked to a conflict receipt. The decision is
either `discard` or `requeue`, with an explanation, actor, and time.
`requeue` records intent only; it never applies or merges the old payload.

### Browser envelope

IndexedDB stores minimal unencrypted routing metadata plus an AES-256-GCM
ciphertext containing the exact package and local queue. Associated data binds
the package UUID and manifest digest. PBKDF2-SHA-256 uses a per-package salt and
310,000 iterations; the passphrase and derived key are not persisted.

See [ADR-0018](../adr/0018-controlled-offline-and-intermittent-operation.md)
and the
[offline operations guide](../operations/offline-and-intermittent-operation.md).
