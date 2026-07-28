# Accounts, authorization, and audit controls

## P1.1 controls

- There is no public account registration endpoint.
- Administrators provision users and installation roles through controlled Django administration.
- Active incident memberships constrain non-administrator incident visibility and changes.
- API authorization comes from the backend policy service; hiding a frontend control is not a security boundary.
- Incidents and operational periods are archived instead of deleted. Memberships are deactivated instead of deleted.
- Source releases are additive and protected from replacement or cascading deletion.
- Material API changes create append-only audit events. Audit details contain identifiers and changed-field names, not passwords, tokens, protected channel values, or request bodies.
- Reference imports require administrator permission, validation, dry-run review, atomic persistence, provenance, and a payload digest.

## P1.6 local-token lifecycle

- Local tokens have a configurable maximum lifetime. `ICT_TOKEN_TTL_SECONDS` defaults to 28,800
  seconds (eight hours) and must be greater than zero.
- Every successful sign-in rotates the user's token, so the previous token stops working.
- Sign-out revokes the current token. The browser also clears its session when the local expiration
  is reached or the API rejects the token.
- Disabling a Django account blocks its token on the next request. A password change alone does not
  revoke an existing token; suspected compromise requires account disablement and controlled token
  revocation.
- Sign-in and sign-out events are append-only and do not include passwords, token values, cookies,
  authorization headers, or request bodies.
- Tokens are header-only credentials and require TLS outside local development. Do not put them in
  URLs, logs, tickets, chat, screenshots, or browser local storage.

See [ADR-0007](../adr/0007-local-token-lifecycle.md) for the decision and accepted non-production
limits.

## Operator responsibilities

- Use unique named accounts; do not share administrator credentials.
- Assign the least-privileged installation and incident roles needed.
- Disable Django staff and active status promptly when access is revoked, and deactivate incident memberships when assignments end.
- Protect database backups and audit records according to the highest classification of data stored in the installation.
- Back up before imports and upgrades, test restoration, and retain backups according to adopted policy.
- Review audit events regularly for unexpected role, incident, membership, archival, or import activity.

## P1.2 plan controls

- `plan.view`, `plan.edit`, `plan.approve`, and `plan.export` remain centralized backend capabilities.
- Approval locks a complete revision and its assignment and relationship children. Later work begins by copying to a new numbered draft.
- Each controlled resource row stores an immutable source/release/digest snapshot so a later library update cannot rewrite an approved plan.
- Remote Base, Link, and Patch relationships are typed records. A Patch requires two or more rows from the same revision.
- Contact name, address, phone, and 24-hour contact fields are optional, incident-scoped, audited by changed field name, and excluded from the P1.2 PDF.
- P1.3 associates assignments with canonical incident site records; P1.2 contact fields do not duplicate those coordinates.
- Only approved revisions can produce the current official PDF endpoint. PDF exports create audit events.

## P1.3 spatial controls

- `site.view`, `site.edit`, and `site.export` remain centralized backend capabilities and inherit incident membership scoping.
- Approval freezes each assignment link's site coordinates, entered-coordinate representation, source identity, retrieval time, and manual rings.
- Approved SVG, KML, GeoJSON, and CSV exports read frozen snapshots rather than mutable canonical sites.
- The default address provider is disabled. Enabling a live geocoder or third-party overlay requires a separate privacy, terms, attribution, reliability, and provenance review.

## P2.1 RF input controls

- Every subscriber profile, profile version, and RF input snapshot operation is incident-scoped
  in backend policy. Browser visibility is not authorization.
- `rf.view`, `rf.edit`, and `rf.approve` are the centralized capabilities. Administrator, COML,
  and COMC defaults include all three; COMT includes view/edit; Contributor and Read-only include
  view. Incident membership still limits non-administrator access.
- Draft versions are editable; approved versions and approval snapshots are immutable. Changes
  create a new numbered draft, and archival preserves history.
- Profile selection is explicit and version-specific. No portable, mobile, fixed, local, band,
  equipment, power, receiver, antenna, gain, loss, height, or calculation default is operationally
  approved.
- Nullable unknown values remain `null`, and controlled values use `unknown`; authorization does
  not permit a service or browser to inject a default.
- `input_basis` marks a whole version as `unknown`, `recorded_fact`, `modeled_assumption`, or
  `mixed`. Nonblank `notes` are required for `mixed` to explain the boundary without adding
  sensitive source material. Entered ERP also requires nonblank source/method notes. The
  implemented contract does not claim per-field provenance.
- Profile create/update/archive, version create/update/copy/approve, and snapshot create/archive
  actions create append-only audit events with actor, incident, target, and changed field names.
  Snapshot-related events include the digest field name where applicable; events do not duplicate
  RF values or notes.
- Snapshot digests detect a changed canonical payload but do not prove source accuracy,
  confidentiality, RF performance, authorization, or coordination approval.
- Qualified COML, COMT, COMC, and RF engineering practitioners must approve field meanings, units,
  provisional ranges, cross-field rules, calculation conventions, and subscriber assumptions
  before operational suitability is claimed.

See the [Phase 2 RF input data model](../data-model/phase-2.md) and
[ADR-0008](../adr/0008-versioned-rf-analysis-inputs-and-subscriber-profiles.md) for the exact
implemented fields, provisional validators, snapshot boundary, and human gate.

## P2.2 elevation and HAAT controls

- `rf.view`, `rf.edit`, and `rf.approve` also govern incident-scoped HAAT listing, calculation,
  retry, and approval. Browser controls are not authorization.
- Provider selection and source approval are server configuration. Requests cannot supply a
  provider class, URL, credential, or allowlist entry.
- The disabled provider is the default. An unapproved configured provider is not called.
- Elevation cache and HAAT records are retained and immutable. Retry and cache refresh create new
  records; approval locks a complete HAAT calculation.
- Create, retry, and approval actions emit append-only audit events. Audit details identify
  changed fields, cache use, superseded result identity, and result digest without duplicating
  incident coordinates, terrain samples, RF inputs, or source credentials.
- Partial, missing, out-of-coverage, unavailable, and stale source states are operator-visible.
  Partial and unavailable calculations cannot be approved.

See [ADR-0009](../adr/0009-source-aware-elevation-and-reproducible-haat.md) and the
[elevation/HAAT operations guide](../operations/elevation-and-haat.md).

## P1.6 append-only audit review

The append-only implementation, request transaction boundary, hash-chain verification, protected
field handling, actor retention, and export-digest boundary have been reviewed against
deterministic abuse cases. See [Append-only audit review and abuse cases](audit-abuse-cases.md)
for the test matrix, operator verification procedure, explicit limitations, and human gates.

## Remaining prototype limitations

The prototype does not yet provide multifactor authentication, password recovery workflows,
external federation, automated CiviCRM eligibility synchronization, or incident-data retention
schedules. Local tokens are bounded and revocable but remain bearer credentials. Audit rows are
hash-chained inside the application database, but there is no external timestamp, signature,
remote audit archive, or automated integrity alert. These risks require explicit security and
operational disposition in the
[non-production release-candidate checklist](../releases/non-production-release-candidate.md).
Security reviewers must accept these limits before any release candidate or hosted use beyond
synthetic data. A candidate remains synthetic-data-only and is not production authorization.
