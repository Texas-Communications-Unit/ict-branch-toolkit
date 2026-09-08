# Issue #121 — Authorized incident and operational-period editing

## Purpose

Define the implementation contract for GitHub Issue #121 so incident names and operational-period metadata can be corrected after creation without weakening authorization, auditability, historical reproducibility, or record relationships.

## Existing contracts to preserve

- Issue #2 owns the established incident lifecycle, policy-backed roles, and audit model.
- Issue #3 owns immutable approved plan revisions.
- Issue #6 owns official export/source-revision integrity.
- Issue #61 owns the WCAG 2.2 Level AA engineering target.
- Issue #23 defines later concurrency semantics; mutations introduced here must not prevent explicit revision/conflict controls later.
- `AGENTS.md` requires incident-scoped authorization, immutable approved revisions, synthetic/public/approved data only, feature-branch work, tests, documentation, and human approval before merge/deployment.

## Implementation slices

### 1. Backend mutation contract

Add or extend authenticated mutation endpoints for incident and operational-period metadata using the existing backend permission classes/services.

Requirements:

- Resolve incident scope from the server-side record relationship, never from a client claim alone.
- Require the existing lifecycle-management/edit permission appropriate to the record.
- Return 403 for authenticated users lacking authority and preserve current authentication semantics for unauthenticated requests.
- Validate mutable fields centrally in serializers/services/models as appropriate.
- Reject blank/whitespace-only names after normalization.
- Enforce valid operational-period date/time relationships, including end >= start when both are present.
- Reject attempts to change immutable identifiers, incident ownership/scope, foreign keys that would move records across incidents, or plan revision identity.
- Use transactions where an audit entry and mutation must commit atomically.
- Return a normalized current representation after a successful update.

### 2. Explicit mutable-field allowlist

Do not expose generic model PATCH behavior without an allowlist.

Initial safe surface should be limited to fields already represented as operator-editable lifecycle metadata. At minimum:

- Incident: display/name field.
- Operational period: display/name/label and supported start/end timestamps already present in the model/API.

If additional fields are discovered during implementation, include them only when they are clearly lifecycle metadata and covered by authorization, validation, tests, audit, and UI behavior. Record materially different fields as separate scope rather than silently expanding the endpoint.

### 3. Audit behavior

Every successful edit must create append-only audit evidence through the existing project audit mechanism.

Record at least:

- actor identity;
- incident identifier/scope;
- object type and stable object identifier;
- changed field names;
- prior and resulting values where policy permits;
- timestamp/action/disposition.

Do not put unrelated protected information into general application logs. If the existing audit event structure stores structured before/after payloads, reuse it rather than creating a competing audit system.

### 4. Historical and approved-output behavior

Editing top-level incident/operational-period display metadata must not rewrite an approved plan revision or previously generated artifact.

Implementation must determine where display metadata is snapshotted today:

- If exports already contain an immutable metadata snapshot, retain it unchanged.
- If an export is reconstructed dynamically from the current incident/period record, add the minimum snapshot/version treatment needed so old official exports remain reproducible or clearly historical.
- A changed incident/period name may be used by later drafts/exports after the change, but prior audit/export evidence must not be silently restated as though the new name existed at the original generation time.

Any required export-integrity correction that materially exceeds this issue should be linked as a follow-up to #6 rather than bypassed.

### 5. Frontend workflow

Add visible edit actions to the existing incident and operational-period management surfaces.

Requirements:

- Only render edit affordances when the current authorization/capability response indicates the user may edit, while still enforcing authorization on the server.
- Pre-populate current values.
- Preserve entered values when validation fails.
- Disable duplicate submissions while a save is pending.
- Show an accessible success status after save and actionable inline validation/server errors after failure.
- Cancel must not mutate the record.
- Restore focus predictably after dialog/form close or successful save.
- Do not require mouse-only interaction or communicate status through color alone.

Prefer the project’s existing form/dialog patterns; do not introduce a second component system solely for this feature.

### 6. Concurrency compatibility

This issue does not need to implement the Phase 3 collaboration framework, but the endpoint should be compatible with it.

Preferred approach:

- If the current API already exposes version/revision/update timestamps suitable for optimistic concurrency, require or preserve them.
- Otherwise keep mutation logic centralized in a service boundary that #23 can later wrap with explicit stale-write detection.
- Do not add silent last-write-wins assumptions to documentation or UI promises.

### 7. API/schema documentation

If new PATCH/PUT endpoints or request/response shapes are introduced:

- update OpenAPI/schema fixtures;
- document editable fields, authorization, validation, and error responses;
- document that stable IDs and relationships are not editable through this workflow.

### 8. Test matrix

Backend tests should cover at least:

1. authorized incident-name update;
2. authorized operational-period update;
3. read-only/unauthorized user denied;
4. cross-incident access denied;
5. blank/invalid name rejected;
6. end-before-start rejected;
7. immutable ID/scope fields cannot be changed;
8. linked plan/site/form relationships remain intact;
9. approved plan revision records remain unchanged;
10. audit event is created with the correct actor/object/changed fields;
11. failure does not create a misleading audit-success event;
12. current representation is returned after save.

Frontend/component/browser tests should cover at least:

1. edit action visibility by capability/role;
2. current values are populated;
3. successful save updates visible text without record recreation;
4. validation failure preserves entered values and associates errors with fields;
5. 403/permission denial is actionable;
6. pending save prevents duplicate submission;
7. cancel leaves values unchanged;
8. keyboard-only operation and focus restoration;
9. screen-reader-accessible status/error feedback;
10. 320 CSS-pixel/reflow behavior where the affected view participates in required browser evidence.

### 9. Verification commands

Run the repository-required checks for the changed surface, including:

- backend formatting/lint;
- Django system and migration checks;
- backend tests;
- frontend formatting/lint/accessibility lint;
- TypeScript type checks;
- frontend component/browser tests;
- frontend build;
- OpenAPI/schema consistency where changed;
- applicable dependency/security/secret/container/workflow checks required by CI.

Automated accessibility checks are engineering evidence, not a WCAG conformance claim.

## Implementation sequencing

1. Inspect current incident/operational-period models, serializers/views/services, permission policy, audit service, and frontend management surface.
2. Define the mutable-field allowlist and reuse the current backend permission identifier.
3. Implement backend update service/API plus audit atomically.
4. Add backend tests before wiring the frontend.
5. Add accessible frontend edit workflows.
6. Add frontend/browser regression tests.
7. Review export/historical metadata behavior and implement only the necessary preservation change; link wider export work to #6 if required.
8. Update schema/docs and run the complete applicable CI-equivalent checks.

## Human review gate

Before merge, a maintainer should verify with synthetic data that:

- a typo in an incident name can be corrected;
- an operational-period label/time can be corrected;
- a read-only user cannot make either change;
- existing plans/sites/forms remain attached to the same stable records;
- approved revisions and previous exports are not silently rewritten;
- audit history shows who changed what;
- keyboard and error workflows remain usable.

## Out of scope

- deleting incidents or operational periods;
- moving an operational period between incidents;
- changing stable record IDs;
- bulk rename operations;
- weakening permission rules;
- implementing Phase 3 real-time collaboration;
- merging, deployment, DNS/secrets changes, or use of real incident/protected data.
