# Phase 1 Data Model

## P1.0 implemented records

- **Incident:** UUID, name, external incident number, lifecycle status, creator, timestamps, and archival marker.
- **OperationalPeriod:** UUID, parent incident, name, start/end timestamps, creator, and archival marker. End must be after start.

Operational deletion is not exposed in the P1.0 user interface. Foreign keys use protective behavior where removal would damage history.

## Planned aggregate boundaries

- Identity and policy: installation, organization, user, role, incident assignment, permission policy.
- Resource library: source, release/version, conventional channel, trunked talkgroup, incident snapshot.
- Plan: ICS-205 plan, immutable revision, ordered assignment, approval/lock event.
- Mapping: radio site, site-assignment relationship, manual ring, entered-coordinate representation.
- Decision support: rule-set version, warning, stable rule ID, evidence and assumptions.
- Audit/export: append-only event, export record, source revision, file digest.

## Invariants

Approved revisions are immutable; official exports reference only approved revisions; resource snapshots retain source/version; frequencies use integer hertz; coordinates use WGS 84; distances use meters; conventional and trunked resources remain distinct; squelch differences do not cancel RF conflict warnings; and audit events are append-only.

