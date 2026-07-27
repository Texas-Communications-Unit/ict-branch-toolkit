# Operation and monitoring

> **NON-PRODUCTION PROTOTYPE:** These controls govern synthetic-data-only
> evaluation. They are not a production service-level objective, security
> authorization, or approval to enter operational data.

The installation administrator owns routine checks. A maintainer owns change
approval, and the organization's security contact owns suspected compromise.
The [account and audit controls](../security/accounts-and-audit.md), [security
policy](../../SECURITY.md), and adopted local policy remain controlling.

## Start-of-use checks

Before each evaluation session, and at least daily while a shared test remains
available:

1. Confirm the approved commit and a clean application checkout.
2. Run `docker compose ... config --quiet` and `docker compose ... ps`.
3. Check the internal and public health endpoints.
4. Confirm the public certificate is valid and HTTP-to-HTTPS behavior is as
   approved.
5. Review backend, frontend, database, and reverse-proxy logs since the previous
   check.
6. Confirm adequate database-volume, container, log, and backup-storage space.
7. Confirm the newest backup and checksum meet the adopted recovery point
   objective (RPO); verify the checksum and archive catalog.
8. Confirm only current named evaluators have active accounts and incident
   memberships.
9. Record the check without copying credentials, tokens, protected values,
   private endpoints, or raw incident content into a public system.

Use the exact Compose file and protected environment file for the installation:

```sh
deploy_env=/path/to/protected/deployment.env
docker compose \
  --env-file "$deploy_env" \
  -f compose.production.yaml \
  ps
docker compose \
  --env-file "$deploy_env" \
  -f compose.production.yaml \
  logs --since 24h backend frontend db
```

Review logs locally before sharing them. Redact credentials, tokens, personal or
incident information, private host names and addresses, and operational
connection details. Report security-sensitive findings privately under
`SECURITY.md`.

## What to monitor

| Signal                           | What it proves                                                                                                   | Escalation condition                                                                                                                                                         |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Public HTTPS home page           | Reverse proxy, certificate, frontend, and basic routing are reachable.                                           | Any sustained failure or unexpected certificate/redirect change.                                                                                                             |
| `/api/health/`                   | Django can execute a database query; PostgreSQL responses also report PostGIS.                                   | Non-`200`, missing `status: "ok"`, wrong database backend, or missing PostGIS.                                                                                               |
| Compose health and restart count | The three application services pass their configured health checks and are not repeatedly restarting.            | `unhealthy`, `exited`, or an unexplained restart.                                                                                                                            |
| Backend and proxy status codes   | Authentication, throttling, authorization, and exception behavior are observable without logging request bodies. | Repeated `500`; an unexplained rise in `401`, `403`, or `429`; or detailed exception text reaching clients.                                                                  |
| Backup age and verification      | A recovery artifact exists within the adopted RPO and its digest/catalog remain valid.                           | Backup older than the adopted RPO, missing checksum, verification failure, or failed scheduled drill.                                                                        |
| Storage and resource use         | The host has room for the database, images, logs, and backups.                                                   | Any local threshold breach or sustained resource exhaustion. Candidate performance evidence must define tested thresholds; do not invent a production limit from this table. |
| Audit chain                      | Existing audit rows remain internally hash-consistent.                                                           | Any failed chain verification, gap, or unexpected privileged event.                                                                                                          |
| External providers               | An approved map or other dependency is behaving within reviewed terms and privacy controls.                      | Provider outage, attribution/privacy failure, unexpected request destination, or terms change. Return to the neutral map when required.                                      |

The health endpoint is intentionally narrow and unauthenticated. It does not
prove that authorization is correct, a user workflow works, backups are recent,
exports are valid, or external providers are available. Use a synthetic
authenticated smoke test after installation, upgrade, or recovery. Availability
targets and tested throughput must come from approved performance evidence
before a candidate is labeled.

## Audit-chain verification

Run the current management procedure inside the backend container:

```sh
deploy_env=/path/to/protected/deployment.env
docker compose \
  --env-file "$deploy_env" \
  -f compose.production.yaml \
  exec -T backend \
  python manage.py shell -c \
  "from apps.audit.services import verify_audit_chain; ok, event = verify_audit_chain(); print({'ok': ok, 'broken_sequence': getattr(event, 'sequence', None)}); raise SystemExit(0 if ok else 1)"
```

`{'ok': True, 'broken_sequence': None}` is the expected result. A passing
internal chain detects modification, deletion, or reordering within the current
database, but it is not an external timestamp, signature, or remote audit-log
archive.

If verification fails, stop changes, restrict external access, preserve the
database and sanitized evidence, and notify the maintainer and security contact.
Do not edit, delete, resequence, or regenerate audit rows to make the check pass.

## Account and data operations

- Use unique named accounts and least-privileged installation and
  incident-scoped roles. There is no public registration.
- Local prototype tokens expire after the configured maximum lifetime, rotate
  at sign-in, and are revoked at sign-out. They remain bearer credentials and
  have no self-service recovery or multifactor protection. Deactivate the user
  and revoke the token through controlled administration when access ends or
  compromise is suspected; changing the password alone does not revoke an
  issued token.
- Archive incidents and operational periods; do not delete history from the
  database.
- Approved revisions are immutable. Copy an approved revision to a new draft
  for later work.
- Apply reference libraries only through the
  [reference import procedure](reference-library-imports.md).
- Treat coverage and deconfliction results as planning decision support, never
  authorization, coordination approval, or a coverage guarantee.
- Use only synthetic data in the prototype. A release candidate does not change
  that boundary.

## Changes, upgrades, and recovery

Every configuration or application change requires a recorded owner, reviewed
diff, backup, rollback decision, maintenance window, and post-change
verification. Use these existing procedures rather than improvising:

- [Installation and configuration](installation-and-configuration.md)
- [Shared test deployment](shared-test-deployment.md)
- [Backup, restore, upgrade, and rollback](backup-restore-and-rollback.md)
- [Map-provider deployment checklist](map-provider-deployment-checklist.md)
- [Export verification](export-verification.md)

Restoration replaces the active database and requires the typed guard in the
recovery script. Never add `--volumes` to a rollback command, reverse a data
migration by assumption, force-push shared history, or reopen access before
post-recovery approval.

## Suspected security or integrity incident

1. Restrict external access without deleting containers, volumes, logs, or
   backups.
2. Record the exact observed time, approved commit, affected service, and
   sanitized symptom.
3. Preserve logs and create a backup if doing so is safe and does not overwrite
   evidence.
4. Rotate exposed credentials through the owning system; never paste them into
   an issue or chat.
5. Use private vulnerability reporting for security details.
6. Restore service only after the maintainer approves the diagnosis, recovery
   point, verification result, and residual risk.
