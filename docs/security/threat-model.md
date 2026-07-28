# Prototype Threat Assumptions

## Assets

Assets include approved communications plans, source/version provenance, user authority,
audit history, site coordinates, versioned RF inputs, subscriber profiles, calculation methods,
approval snapshots and digests, exports, and configuration. The prototype permits synthetic data
only.

## Primary threats

- Unauthorized reading or alteration of drafts and approved information.
- A UI-only control being bypassed through direct API access.
- Secrets or operational data entering source control, logs, fixtures, or screenshots.
- Published information losing its source, approval, or revision linkage.
- Malicious imports, file uploads, map styles, or external integrations.
- Dependency or container compromise.
- Planning warnings being interpreted as technical or legal authorization.
- A modeled RF assumption, provisional range, or subscriber profile being presented as a recorded
  fact or approved operational default.
- An explicit unknown being replaced with zero or a hidden default, creating false precision.
- Transmitter output power being mislabeled as ERP/EIRP or an antenna gain reference being omitted.
- AGL, AMSL, and HAAT being conflated or silently derived with an unapproved terrain method.
- A mutable input/profile change rewriting the meaning of an approved calculation.
- Cross-incident access to RF inputs, profiles, snapshots, or sensitive equipment/site details.
- An unapproved elevation provider receiving incident coordinates or returning misleading terrain.
- Stale, partial, missing, or out-of-coverage terrain being presented as complete.
- Vertical-reference or datum conversion being omitted while apparently precise elevations remain.
- Retry or cache refresh rewriting the source evidence behind an earlier HAAT result.

## Design responses

Enforce policy in the backend, keep approved revisions immutable, retain provenance, use
append-only audit design, validate imports before persistence, isolate external integrations, scan
dependencies/secrets/containers, and label limitations at user and export boundaries. The P1.6
[append-only audit review](audit-abuse-cases.md) records formal audit abuse cases, automated
evidence, and the limits of the local hash chain. Other surfaces must add corresponding abuse
cases and security tests as they are implemented.

For P2.1, use typed canonical units; preserve transmitter power, losses, antenna gain/reference,
and every ERP derivation step; distinguish isotropic and dipole gain references; keep AGL, AMSL,
and HAAT separate; represent unknown values explicitly; and create immutable canonical RF input
snapshots and digests from approved profile versions. P2.2 HAAT calculations bind to the exact
approved snapshot. Version-level `input_basis` distinguishes
`recorded_fact`, `modeled_assumption`, `mixed`, and `unknown`; mixed versions use minimized notes to
explain the boundary. The current contract does not claim per-field provenance.

Every RF input, profile, and snapshot operation must enforce incident scope in backend policy and
create a non-sensitive append-only audit event. No numerical range, default subscriber assumption,
terrain method, or calculation convention is operationally approved until qualified COML, COMT,
COMC, and RF engineering reviewers complete the
[ADR-0008 human gate](../adr/0008-versioned-rf-analysis-inputs-and-subscriber-profiles.md).
Calculated output remains planning decision support, not propagation or coordination authority.

For P2.2, provider selection is server-controlled and exact source descriptors must be
allowlisted before retrieval. The safe default makes no external request. Exact query/sample
snapshots, source and result digests, cache state, transformation metadata, exclusions, warnings,
and method versions are retained. Cache refresh and retry create new immutable evidence. Incident
policy scopes every HAAT result and its elevation snapshot; audit events identify material actions
without duplicating coordinates, RF values, or terrain samples in audit detail. Partial and
unavailable results cannot be approved. See
[ADR-0009](../adr/0009-source-aware-elevation-and-reproducible-haat.md).

