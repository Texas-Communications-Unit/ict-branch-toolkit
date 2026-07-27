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
snapshots and digests from approved profile versions. A future approved analysis must bind to its
exact snapshot. Version-level `input_basis` distinguishes
`recorded_fact`, `modeled_assumption`, `mixed`, and `unknown`; mixed versions use minimized notes to
explain the boundary. The current contract does not claim per-field provenance.

Every RF input, profile, and snapshot operation must enforce incident scope in backend policy and
create a non-sensitive append-only audit event. No numerical range, default subscriber assumption,
terrain method, or calculation convention is operationally approved until qualified COML, COMT,
COMC, and RF engineering reviewers complete the
[ADR-0008 human gate](../adr/0008-versioned-rf-analysis-inputs-and-subscriber-profiles.md).
Calculated output remains planning decision support, not propagation or coordination authority.

