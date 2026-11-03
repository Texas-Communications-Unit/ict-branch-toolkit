# PostGIS 3.5 to 3.6 upgrade

This change keeps PostgreSQL on major version 17. Development, production, CI
database services, and the normal recovery fixture use PostGIS 3.6. The previous
3.5 image remains only as the explicit upgrade/rollback test baseline.

## Approval and recovery prerequisites

Before a production upgrade, verify an independent encrypted recovery copy and
complete the isolated restore drill. A local pre-deployment dump on the same VM
is not sufficient protection against losing the VM or data disk. The ordinary
protected deployment approval still applies. Preserve the matched database,
attachments, environment, source commit, and image identity using the
[recovery runbook](backup-restore-and-rollback.md).

Do not merge the two original image-only proposals independently: this change
coordinates those image references with the existing-database SQL upgrade and
its recovery evidence. No Python or MGRS upgrade is included.

## Startup upgrade

The backend startup command runs `python manage.py upgrade_postgis` before
ordinary Django migrations, imports, or Gunicorn. Non-GIS databases are skipped.
The spatial database must already contain the core PostGIS extension.

The command serializes concurrent starts with a PostgreSQL transaction advisory
lock, inventories installed PostGIS extensions and their available versions,
and accepts only stable 3.5/3.6 installed versions with stable 3.6 targets. An
unexpected major/minor, prerelease target, missing target, incomplete upgrade,
or changed extension inventory stops startup. It uses the vendor's
`postgis_extensions_upgrade()` helper and verifies every inventoried extension
matches its available target. The transaction rolls back on verification failure.
Already-current extensions do not repeat the upgrade.

Replacing the image alone does not establish that SQL extension definitions have
been upgraded. Confirm both `pg_extension.extversion` and the library/build report:

```sql
SELECT extname, extversion FROM pg_extension
WHERE extname IN ('postgis', 'postgis_raster', 'postgis_sfcgal',
                 'postgis_topology', 'postgis_tiger_geocoder');
SELECT postgis_full_version();
```

Only already-installed extensions are managed; this is not authorization to add
new capabilities. References: [PostGIS extension upgrade](https://www.postgis.net/docs/PostGIS_Extensions_Upgrade.html)
and [upstream container upgrade helper](https://github.com/postgis/docker-postgis/blob/master/update-postgis.sh).

## Required evidence

The installed-stack workflow builds the actual derived candidate database image
and backend, starts the normal production stack, and exercises the synthetic
application/recovery tests. Its additional isolated upgrade fixture:

1. Initializes PostgreSQL 17/PostGIS 3.5 on a uniquely named test volume with
   synthetic geometry, geography, a spatial index, and a custom spatial reference.
2. Creates a checksum-verified custom-format pre-upgrade dump.
3. Reopens that **same test volume** using the derived 3.6 database image and
   confirms the SQL version is still 3.5 before the startup command upgrades it.
4. Runs the candidate backend's upgrade command, checks all installed extension
   versions, exact stored geometry/geography bytes, records, index, and custom
   spatial reference, then verifies a second invocation is idempotent.
5. Restores the old dump into a separate clean 3.6 volume and verifies preservation.
6. Restores the same old dump into a separate clean 3.5 volume to prove the rollback
   path. It never opens the upgraded volume with old binaries.

The fixture exposes no host ports, uses an isolated internal Docker network and
synthetic credentials, and cleans up only its own exact generated resource names.
Sanitized results are retained as `postgis-upgrade.json` with installed-stack
evidence. Production images must still pass the normal security scans.

## Production verification and rollback

After approved deployment, verify the installed commit, extension SQL and library
versions, healthy containers and public API, sign-in/authorization, site coordinate
operations, and an operator-viewed map. Keep sensitive records out of evidence.

If schema/library compatibility fails after extension changes, restore the matched
pre-upgrade recovery set into the approved prior database/runtime configuration.
Do not attempt a binary/image downgrade against the upgraded data volume. A
successful application migration rollback test is not a PostGIS downgrade test.
