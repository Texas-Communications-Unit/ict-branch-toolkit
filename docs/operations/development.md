# Development Operations

## Startup and health

Copy `.env.example` to `.env`, change the local administrator password, and run `docker compose up --build --wait`. Verify `docker compose ps` and `curl http://localhost:8000/api/health/`. The health response must report PostgreSQL and a PostGIS version for the integration environment.

The development Compose file explicitly builds the backend `development`
target, which includes the pinned test, audit, lint, and formatting tools used by
the Makefile. The production Compose file builds the separate `production`
target with runtime dependencies only. Do not add development tools to the
production target to make a local command available. The production image also
excludes Python package installers and build backends; its dependencies are
assembled in an intermediate image and copied into the final runtime image.

## Backup and restore boundary

P1.0 contains synthetic data only. The controlled test-deployment procedure
specifies integrity verification, isolated restore testing, encrypted-storage
requirements, retention, and initial recovery objectives. Follow the
[backup, restore, upgrade, and rollback runbook](backup-restore-and-rollback.md);
do not improvise against an active database.

## Reset and rollback

`make reset` removes this project's Compose services and named development volume. Confirm the Compose project name and that no needed synthetic work remains before running it. Code rollback uses normal Git reversal on a feature branch; do not rewrite shared history. Django migrations must remain reversible where supported.

## Logs

Use `docker compose logs backend frontend db`. Do not paste logs into public issues until they have been reviewed for credentials, tokens, personal information, incident information, hostnames, and private endpoints.
