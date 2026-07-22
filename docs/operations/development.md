# Development Operations

## Startup and health

Copy `.env.example` to `.env`, change the local administrator password, and run `docker compose up --build --wait`. Verify `docker compose ps` and `curl http://localhost:8000/api/health/`. The health response must report PostgreSQL and a PostGIS version for the integration environment.

## Backup and restore boundary

P1.0 contains synthetic data only. For developer convenience, `pg_dump` and `pg_restore` may be run inside the database container, but this is not yet a production backup procedure. P1.6 must specify encryption, retention, integrity verification, restore testing, and recovery objectives.

## Reset and rollback

`make reset` removes this project's Compose services and named development volume. Confirm the Compose project name and that no needed synthetic work remains before running it. Code rollback uses normal Git reversal on a feature branch; do not rewrite shared history. Django migrations must remain reversible where supported.

## Logs

Use `docker compose logs backend frontend db`. Do not paste logs into public issues until they have been reviewed for credentials, tokens, personal information, incident information, hostnames, and private endpoints.

