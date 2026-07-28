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

## P3.1 terrain-analysis controls

- `rf.view`, `rf.edit`, and `rf.approve` govern incident-scoped terrain
  listing/retrieval, queue/run/cancel/retry, and approval. Browser controls are
  not authorization.
- Provider, dataset, engine, and approval selection are server configuration.
  Requests cannot supply a provider class, URL, credential, dataset, or
  allowlist object.
- Queueing binds one complete approved Phase 2 estimate, its exact HAAT
  evidence, site, source descriptor, provider configuration, engine
  capabilities, parameters, application version, and digest.
- Inputs and completed results are immutable and retained. Cancelled/failed
  retry creates a new `supersedes` record. Direct update and hard deletion are
  rejected.
- Partial, unsupported, stale, failed, and cancelled evidence cannot be
  approved. Approval of complete current evidence does not approve the source,
  method, coverage, coordination, or operational decision.
- Terrain audit events retain record/source/method identifiers, lifecycle
  states, and digests without duplicating coordinates, profile samples, RF
  values, provider credentials, raw responses, or protected incident content.

See [ADR-0017](../adr/0017-optional-source-aware-terrain-analysis.md) and the
[terrain operations guide](../operations/terrain-analysis.md).

## P2.5 field evidence and calibration controls

- `rf.view`, `rf.edit`, and `rf.approve` govern incident-scoped observation, review, calibration
  creation, and calibration approval. Browser controls are not authorization.
- Observation create events record field names, source linkage IDs, and the canonical input digest
  without copying coordinates, measurements, observer/source text, or notes.
- Approval and exclusion create separate append-only review records and audit events. Correction
  creates a new observation linked through `supersedes`.
- Calibration create and approval events retain selected count and observation/result digests
  without duplicating field evidence.
- Direct update or deletion of observations, reviews, calibration sets, and membership links is
  rejected.

See [ADR-0012](../adr/0012-field-observations-and-incident-local-calibration.md) and the
[field observation and calibration guide](../operations/field-observations-and-calibration.md).

## RF deconfliction controls

- `rf.view`, `rf.edit`, and `rf.approve` govern incident-scoped deconfliction listing, creation,
  and approval. Browser controls are not authorization.
- Creation requires an approved ICS-205 revision owned by the selected active incident. Active
  resources are checked for omission only when the user explicitly selects them.
- Analyses, input snapshots, result snapshots, and digests are retained and immutable. A changed
  plan, resource selection, source release, frozen area, or rule version requires a new analysis.
- Approval fails closed unless the exact rule-set version is server-allowlisted and the retained
  input and result digests reproduce.
- `deconfliction_analysis.created` and `deconfliction_analysis.approved` audit events record the
  analysis, revision, rule-set version, counts, and digests. They do not copy frequencies,
  squelch values, coordinates, site snapshots, selected-resource content, or warnings.
- A warning or absence of warnings remains decision support. It does not provide frequency
  coordination, spectrum authorization, propagation evidence, interference protection, or
  incident-command approval.

See [ADR-0015](../adr/0015-versioned-rf-deconfliction-decision-support.md) and the
[RF deconfliction operations guide](../operations/rf-deconfliction.md).

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
