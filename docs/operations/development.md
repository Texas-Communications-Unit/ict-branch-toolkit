# Development Operations

## Startup and health

Copy `.env.example` to `.env`, change the local administrator password, and run `docker compose up --build --wait`. Verify `docker compose ps` and `curl http://localhost:8000/api/health/`. The health response must report PostgreSQL and a PostGIS version for the integration environment.

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
