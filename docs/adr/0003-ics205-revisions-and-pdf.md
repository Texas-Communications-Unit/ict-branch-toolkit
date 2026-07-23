# ADR-0003: ICS-205 revision and PDF boundaries

- Status: Accepted for P1.2
- Date: 2026-07-23
- Decision owners: Maintainers

## Context

ICS-205 drafting needs ordered rows, copy-forward, typed row relationships, sensitive optional contacts, source provenance, approval locking, comparison, and a first deterministic PDF. Approved information must not change when users edit later work.

## Decision

Use an `ICS205Plan` aggregate for one incident and operational period. Numbered `PlanRevision` records own assignments and relationships. Only drafts accept mutations. Approval records the actor and time and locks the revision and children; copy-forward creates a new draft with independent rows and relationships.

Assignments may reference one controlled conventional channel or trunked talkgroup and always retain an immutable JSON source snapshot. Incident-created rows retain an explicit incident source marker. Remote Base, Link, and Patch are typed relationships; Patch requires at least two rows from the same revision.

The backend is authoritative for `plan.view`, `plan.edit`, `plan.approve`, and `plan.export`. Official PDF output is available only for approved revisions and is generated deterministically with ReportLab. P1.2 excludes optional contact fields from the PDF. P1.3 will supply canonical site coordinates.

## Consequences

Historical approvals and resource provenance survive later edits and library updates. Copy-forward duplicates a bounded plan revision, increasing storage in exchange for simple auditability. The first PDF is FEMA-style rather than a claim of final pixel fidelity; qualified semantic and visual review remain human gates.

## Alternatives considered

Mutable plans with event reconstruction were rejected because correct historical rebuilding would be harder to verify. Storing assignments only as JSON was rejected because ordering, relationships, authorization, and validation require explicit records. Editing the official FEMA PDF template directly was deferred until maintainers approve final form fidelity and redistribution boundaries.
