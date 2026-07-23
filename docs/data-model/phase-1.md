# Phase 1 Data Model

## Implemented records

- **Incident:** UUID, name, external incident number, lifecycle status, creator, timestamps, and archival marker.
- **OperationalPeriod:** UUID, parent incident, name, start/end timestamps, creator, and archival marker. End must be after start.
- **UserRoleAssignment:** one configurable installation role per user using the Administrator, COML, COMC, COMT, Contributor, and Read-only defaults.
- **IncidentMembership:** one active or inactive incident-scoped role assignment per user and incident.
- **AuditEvent:** append-only actor, action, target, timestamp, and non-sensitive structured details.
- **ResourceSource:** source type, stable slug, name, and authoritative URL.
- **ResourceRelease:** immutable source/version, release date, effective status, content digest, importer, and import timestamp.
- **ConventionalChannel:** release-scoped channel with integer-hertz RX/TX values, bandwidth, mode, squelch display values, restrictions, and status.
- **TrunkedTalkgroup:** release-scoped system/talkgroup identifier, mode, restrictions, and status; never stored as a conventional channel.
- **ResourceImport:** importer, payload digest, counts, release, and timestamp for an applied atomic import.
- **ICS205Plan:** one plan aggregate per incident and operational period.
- **PlanRevision:** numbered draft or approved revision with preparer, copy source, creator, and approval evidence.
- **Assignment:** stable ordered row with optional controlled resource link, immutable source snapshot, technical display values, structured note, free-text remarks, and optional protected contact fields.
- **AssignmentRelationship:** typed Remote Base, Link, or Patch relationship whose members must belong to one revision; Patch requires at least two rows.

Operational deletion is not exposed. Incidents and periods are archived, memberships are deactivated, source releases remain immutable, approved plan revisions and their children are locked, audit records are append-only, and foreign keys use protective behavior where removal would damage history.

## Planned aggregate boundaries

- Identity and policy: installation, organization, user, role, incident assignment, permission policy.
- Resource library: source, release/version, conventional channel, trunked talkgroup, incident snapshot.
- Plan: implemented ICS-205 plan, immutable revision, ordered assignment, typed relationship, approval/lock event; P1.3 adds canonical sites.
- Mapping: radio site, site-assignment relationship, manual ring, entered-coordinate representation.
- Decision support: rule-set version, warning, stable rule ID, evidence and assumptions.
- Audit/export: append-only event, export record, source revision, file digest.

## Invariants

Approved revisions are immutable; official exports reference only approved revisions; resource snapshots retain source/version; frequencies use integer hertz; coordinates use WGS 84; distances use meters; conventional and trunked resources remain distinct; squelch differences do not cancel RF conflict warnings; and audit events are append-only.

