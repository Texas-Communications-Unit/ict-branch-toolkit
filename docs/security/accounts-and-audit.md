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

## Remaining prototype limitations

P1.1 tokens do not expire automatically and the prototype does not yet provide multifactor authentication, password recovery workflows, external federation, automated deprovisioning, tamper-evident remote audit export, or incident-data retention schedules. Do not treat this milestone as production authorization. P1.6 must resolve or formally accept these risks before a release candidate.
