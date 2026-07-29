# Phase 3 terrain-analysis data model

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

## P3.3 online collaboration

P3.3 adds online-only optimistic collaboration evidence without changing or
requiring the P3.1 terrain aggregate:

| Record                               | Purpose                                                                                                                                                                                                                         |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `PlanRevision.collaboration_version` | Versions revision metadata and the shared assignment collection.                                                                                                                                                                |
| `Assignment.collaboration_version`   | Allows unrelated assignment rows to be edited independently.                                                                                                                                                                    |
| `CollaborationChange`                | Retains client mutation UUID/device, incident/revision, actor, operation, base/resulting versions, affected field names, protected proposed/current snapshots, payload digest, result, and saved/conflict/rejected disposition. |
| `CollaborationResolution`            | Append-only discard, reapply, or intentional replacement decision linked to one retained conflict and optional saved replacement.                                                                                               |
| `PresenceLease`                      | Short-lived incident/revision/section viewing or editing indicator; it is not a lock.                                                                                                                                           |
| `SensitiveFieldRule`                 | Versioned per-incident read/edit roles and omitted/redacted behavior for a documented restricted assignment field.                                                                                                              |
| `ExternalIdentity`                   | Minimal local shadow for a future approved provider; stable subject/contact linkage, eligibility, mapped role, assertion digest, refresh/validity, and disablement state.                                                       |

Approved revisions remain immutable. Collaboration records and resolutions are
retained; presence leases are intentionally ephemeral. Protected snapshots stay
in the incident database and are filtered on every response. Audit events use
metadata and digests instead of copying protected values.

See [ADR-0018](../adr/0018-online-collaboration-and-disabled-external-identity.md)
and the [operator guide](../operations/online-collaboration.md).

## P3.4 governed tools and reports

P3.4 adds a code-defined extension registry and retained execution boundary:

| Record                  | Purpose                                                                                                                                                                                                                 |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ExtensionInstallation` | Stores an Administrator-installed manifest snapshot, exact extension/contract versions, manifest digest, enabled state, actors, and timestamps. Installations begin disabled and cannot be deleted.                     |
| `ExtensionExecution`    | Retains the incident, approved source revision, exact extension/capability/version, canonical input/result snapshots and digests, output classification, actor/time, and complete or bounded failed state. Executions are immutable and cannot be deleted. |

The manifest declares capability, permission, incident/revision scope,
input/output schema, validation, audit, export, source records, approval
requirements, sensitivity, retention, version, failure isolation,
accessibility, and official-output state. The registry has no arbitrary
executable upload or dynamic import path.

The initial `synthetic-readiness-summary` entry provides one non-operational
tool and report. It reads approved ICS-205 assignment metadata/counts and never
copies frequency values or protected contact fields into output. Output is
always `decision_support`; the example cannot create an official form or
approval.

Contract `1.0` is negotiated explicitly. A run fails closed when the requested
contract, installed version, or installed manifest digest differs from the
current registry. Every run rechecks active incident membership and
`extension.run`; export rechecks `extension.view`. General audit detail records
only identifiers, versions, classifications, and digests.

See [ADR-0019](../adr/0019-governed-planning-extension-framework.md) and the
[operator guide](../operations/planning-extension-framework.md).
