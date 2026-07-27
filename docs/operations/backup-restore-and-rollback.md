# Backup, restore, upgrade, and rollback

This runbook applies to the containerized ICT Branch Toolkit test deployment.
It does not authorize operational or protected data. A maintainer must approve
every upgrade, restore, rollback, and retention-policy change.

## Recovery objectives and ownership

For the synthetic shared-test system, the initial targets are:

- recovery point objective (RPO): no more than 24 hours of synthetic changes;
- recovery time objective (RTO): four hours after the application host,
  credentials, and an intact backup are available;
- owner: the installation administrator designated by the maintainer;
- test frequency: an isolated restore drill before every upgrade and at least
  quarterly while the test deployment is active.

These are tested targets, not guarantees. An organization must adopt its own
objectives before permitting non-synthetic data.

## Backup controls

The database is the authoritative persistent application state. The protected
deployment environment file, reverse-proxy configuration, approved commit SHA,
and certificate-reissuance instructions are also required for recovery, but
must not be stored in this public repository.

Create a database backup on the application host:

```sh
cd "$HOME/apps/ict-branch-toolkit"
scripts/database-recovery.sh backup
```

The command:

- creates a PostgreSQL custom-format dump without ownership or privilege
  statements;
- writes the dump and SHA-256 checksum with mode `0600`;
- validates the checksum and archive catalog before reporting success;
- refuses to run unless the protected environment, Compose configuration, and
  database service are available.

The local backup directory is staging space, not the only backup location.
Copy each approved backup and its checksum to organization-approved encrypted
storage using a channel that encrypts data in transit. Encryption keys must be
stored separately from the backup. Keep at least one recovery copy outside the
application host's failure domain.

For the synthetic shared test, retain:

- seven daily backups;
- four weekly backups;
- the last pre-upgrade backup until the next upgrade and restore drill pass.

Delete expired copies through the approved storage system so its audit and
retention controls apply. Do not add an unaudited repository cleanup script.
Adopted records-retention, incident, legal-hold, and data-classification rules
override this test schedule.

## Verification and isolated restore drill

Verify an archive and checksum without restoring it:

```sh
scripts/database-recovery.sh verify /secure/path/postgresql-YYYYMMDDTHHMMSSZ.dump
```

Run an isolated restore drill:

```sh
scripts/database-recovery.sh drill /secure/path/postgresql-YYYYMMDDTHHMMSSZ.dump
```

The drill creates a temporary database in the existing PostgreSQL container,
restores the archive with stop-on-error behavior, confirms that the Django
migration ledger is readable and non-empty, and then drops the temporary
database. It does not replace the active database.

Record the backup timestamp and checksum, application commit, PostgreSQL/PostGIS
versions, start and finish time, result, operator, and follow-up issue. Do not
publish environment values, host details, credentials, or database contents.

## Controlled upgrade

1. Confirm the target is the reviewed commit currently approved on `main`.
2. Read all release notes, dependency changes, migrations, and configuration
   changes between the deployed and target commits.
3. Confirm the working tree is clean and the protected environment file is
   backed up through an approved secret-management process.
4. Create a pre-upgrade database backup and run an isolated restore drill.
5. Record the deployed commit, database backup path and checksum, Compose image
   identifiers, and reverse-proxy configuration backup.
6. Build the target images without replacing the running containers.
7. Schedule the maintenance window and prevent user changes.
8. Deploy through the protected GitHub environment. The backend entrypoint runs
   `migrate --noinput` before starting Gunicorn.
9. Verify container health, the internal and public health endpoints, sign-in,
   incident access, audit-chain verification, and one synthetic export.
10. Retain the pre-upgrade backup until the next approved recovery checkpoint.

## Database restore

Restoration replaces the active database and causes downtime. First disable
external access at the application virtual host or approved maintenance control.
Confirm the archive checksum and run the isolated drill.

The restore command requires the exact database name as a typed guard:

```sh
scripts/database-recovery.sh restore \
  /secure/path/postgresql-YYYYMMDDTHHMMSSZ.dump \
  RESTORE:ict_toolkit
```

The command verifies the requested backup, creates and verifies an emergency
pre-restore backup, stops the backend and frontend, recreates only the configured
application database, restores with stop-on-error behavior, and restarts the
application health checks. It never removes the PostgreSQL volume.

If restoration fails, leave external access disabled. The application services
remain stopped unless restoration reached the successful restart step. Preserve
the failed archive, checksum, logs, and emergency backup; review them for
sensitive content before attaching anything to a public issue.

After restoration:

1. verify the active commit matches the database schema represented by the
   restored backup;
2. verify container, internal, and public health;
3. run the [audit-chain verification procedure](../security/audit-abuse-cases.md#operational-verification);
4. test sign-in, incident-scoped authorization, and a synthetic export;
5. re-enable external access only after maintainer approval.

## Application and migration rollback

Do not force-push, rewrite shared history, delete the database volume, or assume
every Django migration can be reversed. Data migrations may intentionally have
no safe reverse operation.

For a failed upgrade:

1. disable external access and record the failed commit and image identifiers;
2. preserve logs and create a post-failure backup if the database remains
   readable;
3. restore the pre-upgrade database backup using the guarded procedure above;
4. switch the server checkout only to the previously recorded approved commit
   using a fast-forward or detached approved-commit checkout appropriate to the
   deployment process;
5. rebuild and start the Compose stack from that commit;
6. complete all post-restore verification before reopening access.

Database restore plus the previous application commit is the supported migration
rollback. Running `manage.py migrate <app> <older-migration>` against the active
database is not an approved general rollback method.

## Automated evidence

CI creates a custom-format dump of the synthetic PostGIS test database, verifies
its SHA-256 checksum and archive catalog, restores it into a separate temporary
database, and verifies a synthetic marker, the Django migration count, and the
restored PostGIS extension. This confirms that the current schema can complete
the backup and isolated-restore path without replacing the CI source database.
