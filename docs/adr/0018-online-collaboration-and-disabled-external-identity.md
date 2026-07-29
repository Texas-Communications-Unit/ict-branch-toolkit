# ADR-0018: Online collaboration and disabled external identity

- **Status:** Accepted for synthetic online-collaboration development only
- **Date:** 2026-07-28
- **Issue:** #23

## Context

The Toolkit needs multiple incident-assigned users to work in one server-hosted
ICS-205 without silent last-write-wins behavior. Eric selected online,
server-based operation only; the abandoned P3.2 offline branch and its queued
edit/reconnect model are not prerequisites for this decision.

TX-COMU users should eventually authenticate with one WordPress/CiviCRM-backed
credential set. The Toolkit must remain independently deployable, must never
receive or proxy a WordPress password, and must keep incident assignments,
approvals, conflicts, and audit evidence locally. The exact identity protocol,
role mapping, session lifetime, outage window, revocation policy, and
break-glass controls still require security and privacy approval.

## Decision

### Online concurrency

- `PlanRevision` and each ICS-205 `Assignment` have independent positive
  collaboration versions.
- A collaboration mutation supplies a unique client mutation UUID, device UUID,
  target, base version, operation, section, and proposed fields.
- The backend locks the target row, compares the submitted base version, and
  saves only when it still matches. A stale write creates a retained conflict;
  it never overwrites the current value.
- Assignment edits on different records can succeed from the same starting
  state. Creation and reorder use the revision version because they change the
  shared assignment collection.
- Replayed mutation UUIDs are idempotent only when actor, device, and canonical
  payload digest match. Reuse for a different payload is rejected.
- Saved, conflicting, and validation-rejected attempts are retained in
  `CollaborationChange`. A user's later discard, reapply, or intentional
  replacement is a separate append-only `CollaborationResolution`.
- Approved revisions remain immutable. Users must copy an approved plan into a
  new draft before editing.

The browser uses these versioned mutation endpoints for assignment creation,
deletion, and reorder. It shows current and proposed conflict values and asks
the user whether to keep the saved values or intentionally apply the retained
proposal.

### Presence and transport

Presence is a short-lived server lease, not an edit lock. The browser heartbeats
and polls every 20 seconds; the default lease expires after 75 seconds. Polling
and normal manual refresh are the correctness baseline. No WebSocket service or
offline change queue is required.

Presence contains only display name, incident role, section, allowlisted
row/field location, viewing/editing state, and whether the record belongs to
the requester. The API does not expose the internal device identifier,
sequence, or exact lease timestamps. It does not contain form values,
coordinates, contact details, credentials, or keystroke/activity telemetry.

### Authorization and restricted fields

Every collaboration request rechecks current incident membership and backend
policy. Restricted ICS-205 contact fields are filtered before serialization and
checked independently for edits. A controlled per-incident
`SensitiveFieldRule` can assign separate read and edit roles and choose omission
or an explicit `Access restricted` marker.

The approved default allows Administrator, COML, COMC, and COMT to view and
edit restricted contact fields. AUXCOMM and INCM are distinct assignable roles
with the Contributor baseline; those three roles and Read-only fail closed
unless an approved incident rule grants access. Restricted contact fields are
omitted from the official ICS-205 unless an authorized planner explicitly
selects populated fields, records a purpose, and an approver confirms the
matching approval-preview digest.

Audit events record actor, target, operation, affected field names, versions,
disposition, and canonical payload digest. General audit detail does not copy
the protected field values.

### External identity boundary

The repository includes:

- a disabled external-provider class with authorization-code-shaped methods;
- a status endpoint that states live transport and password passthrough are
  unavailable;
- a local `ExternalIdentity` shadow record keyed by stable external subject and
  CiviCRM contact identifiers; and
- deterministic provisioning logic that creates an unusable local password,
  fails closed on expired/ineligible/ambiguous mappings, and stores a digest of
  the asserted attributes.

No authorization endpoint, code exchange, WordPress/CiviCRM network client,
provider credential, live role mapping, outage cache, or session activation is
implemented. The disabled contract names the controlled CiviCRM group `ICT
Branch Toolkit — Access`, controlled role field `ICT Branch Toolkit Role`,
15-minute identity refresh, four-hour maximum outage grace, and exact allowed
role values. Configuration cannot turn the disabled provider into a live
connection.

Administrators can create individually attributable local contingency accounts
with one-time temporary credentials, required reasons, global/default roles,
and optional incident memberships. Users must replace the temporary credential
before sign-in. Disablement and explicit session revocation remove the current
token, and retained audit records preserve attribution. A future reviewed SSO
link must attach to the same local user rather than replace its history.

## Consequences and limits

The server can retain evidence for conflicts and remain correct without a
real-time transport. Independent assignment rows do not block each other, while
shared collection changes can surface a conservative conflict.

This slice is not the complete Issue #23 security gate. Search, attachment,
notification, all derived-output restricted-field handling, deployment concurrency, and live
session revocation still require broader testing. Existing non-collaboration
plan routes remain for compatibility and auditing; supported multiuser browser
editing must use the collaboration mutation API.

Before activation beyond synthetic testing, reviewers must approve the role and
field matrix, presence semantics, export rules, scaling limits, identity
protocol, exact CiviCRM mappings, session/outage/revocation policy, service
identity, and break-glass procedure.
