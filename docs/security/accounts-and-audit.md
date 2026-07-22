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

## Remaining prototype limitations

P1.1 tokens do not expire automatically and the prototype does not yet provide multifactor authentication, password recovery workflows, external federation, automated deprovisioning, tamper-evident remote audit export, or incident-data retention schedules. Do not treat this milestone as production authorization. P1.6 must resolve or formally accept these risks before a release candidate.
