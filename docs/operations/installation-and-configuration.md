# Installation and configuration

> **NON-PRODUCTION PROTOTYPE:** This procedure is for synthetic-data-only
> evaluation. It is not production deployment guidance and does not authorize
> real incident, protected channel, personal, credential, or private
> infrastructure data.

The documented evaluation target is the repository's containerized
PostgreSQL/PostGIS, Django, and React stack. Local contributor setup remains in
the [README](../../README.md#p10-quick-start). A network-accessible evaluation
must also follow the [shared test deployment runbook](shared-test-deployment.md).

## Human gates before installation

A maintainer must approve the exact commit or non-production release candidate
before it is installed anywhere other than a contributor workstation. The
installation owner must also confirm:

- the environment is isolated from production systems and contains only
  synthetic, public, or explicitly approved reference data;
- a named administrator and a named backup/recovery owner are assigned;
- the host, reverse proxy, TLS certificate, protected configuration, firewall,
  encrypted backup storage, and maintenance window are organization-controlled;
- no WordPress, CiviCRM, website, or unrelated application database, document
  root, process, or secret will be shared;
- installation does not imply approval to merge, publish a release, deploy a
  later change, or use non-synthetic data.

When evaluating a release candidate, verify its exact commit and artifact
checksums using the
[non-production release-candidate process](../releases/non-production-release-candidate.md).
A branch name, pull request, mutable container tag, or unverified archive is not
a release identity.

## Prerequisites

- Git, when installing from a reviewed checkout.
- Docker Engine and the Docker Compose v2 plugin.
- At least 4 GB of memory available to Docker for local evaluation.
- A dedicated application directory and a protected deployment environment
  file outside the repository.
- For network access, a trusted reverse proxy and certificate. The application
  port must be reachable only from the approved proxy or evaluation network.
- Approved encrypted storage outside the application host for database backups
  and checksums.

Use the operating-system and Docker versions approved by the installation
owner. Record those versions as installation evidence; this repository does not
currently declare a production-supported operating-system matrix.

## Protected configuration

`.env.example` contains development values only. Do not copy it unchanged to a
shared system. Create the deployment environment file outside the checkout,
restrict it to the deployment account, and back it up through the approved
secret-management process.

Required deployment values:

| Setting                                                                            | Purpose and constraint                                                                                                                                                                                 |
| ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`                                | Dedicated Toolkit database identity. Use a generated password and do not reuse another application's database or credentials.                                                                          |
| `DJANGO_SECRET_KEY`                                                                | Generated secret unique to the installation. Changing it can invalidate Django-signed state.                                                                                                           |
| `DJANGO_ALLOWED_HOSTS`                                                             | Exact public host name plus the internal `backend` health-check host. Do not use a wildcard.                                                                                                           |
| `DJANGO_CORS_ALLOWED_ORIGINS`                                                      | Exact HTTPS browser origin. Do not use a wildcard.                                                                                                                                                     |
| `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL`, `DJANGO_SUPERUSER_PASSWORD` | Seeds the first local administrator. Startup does **not** update an existing user's password when these values later change; rotate the account through a controlled account-administration procedure. |
| `APP_BIND_ADDRESS`, `APP_PORT`                                                     | Dedicated listener used by the reverse proxy. Do not expose the database or backend container directly.                                                                                                |

Security and policy settings:

| Setting                          | Default           | Operational rule                                                                                                                                                                                     |
| -------------------------------- | ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `DJANGO_FORCE_HTTPS`             | `false`           | Set to `true` only after the trusted proxy sends `X-Forwarded-Proto: https` and HTTPS has been verified.                                                                                             |
| `DJANGO_HSTS_SECONDS`            | `31536000`        | Applies only when HTTPS enforcement is enabled. The current application also adds `includeSubDomains` and `preload`; use a staged, maintainer-approved value and rollback plan before increasing it. |
| `DJANGO_THROTTLE_ANON_RATE`      | `30/min`          | Anonymous API request limit. Changes require synthetic load evidence and security review.                                                                                                            |
| `DJANGO_THROTTLE_USER_RATE`      | `300/min`         | Authenticated-user API request limit. Do not raise it merely to suppress alerts.                                                                                                                     |
| `DJANGO_THROTTLE_AUTH_RATE`      | `10/min`          | Stricter token-issuance limit. Repeated `429` responses may indicate bad clients or credential guessing.                                                                                             |
| `ICT_IDENTITY_PROVIDER`          | `local`           | `local` is the only implemented provider. Any other value must fail closed.                                                                                                                          |
| `ICT_TOKEN_TTL_SECONDS`          | `28800`           | Maximum local-token lifetime in seconds. Must be greater than zero. Shortening it can immediately expire existing sessions.                                                                          |
| `ICT_ROLE_POLICY_OVERRIDES`      | `{}`              | JSON policy overrides. Review with least privilege and test incident-scoped authorization before use.                                                                                                |
| `ICT_APPROVED_REFERENCE_IMPORTS` | `[]`              | Exact, checksum-pinned approval objects only. Follow the [reference import runbook](reference-library-imports.md).                                                                                   |
| `ICT_GEOCODER_PROVIDER`          | disabled provider | Keep disabled unless a separate privacy, terms, reliability, and provenance review approves a provider implementation.                                                                               |

The neutral, network-free map is the default. Enabling any external map requires
the [map-provider deployment checklist](map-provider-deployment-checklist.md)
and complete `VITE_MAP_*` metadata. Browser-visible map tokens must be
public-client scoped; management keys and provider secrets must never be placed
in frontend build arguments.

## Build and start

From the approved checkout or verified source artifact:

```sh
deploy_env=/path/to/protected/deployment.env
docker compose \
  --env-file "$deploy_env" \
  -f compose.production.yaml \
  config --quiet
docker compose \
  --env-file "$deploy_env" \
  -f compose.production.yaml \
  build
docker compose \
  --env-file "$deploy_env" \
  -f compose.production.yaml \
  up --detach --wait
```

The backend startup runs database migrations, ensures that the configured
administrator exists, conditionally imports the exact approved bundled NIFOG
release, collects static files, and then starts Gunicorn. Therefore, starting a
new application commit can be a database upgrade. After the first installation,
use the [controlled upgrade procedure](backup-restore-and-rollback.md#controlled-upgrade)
instead of running an unreviewed rebuild.

## Installation verification

Do not accept a running container as sufficient evidence. Record the candidate
commit, Compose image identifiers, configuration review, date, operator, and
results of these checks:

1. `docker compose ... config --quiet` succeeds without printing secrets.
2. `docker compose ... ps` reports the database, backend, and frontend healthy.
3. The internal health path returns JSON with `status: "ok"`,
   `database: "postgresql"`, and a non-empty `postgis` value.
4. The public HTTPS health path succeeds and HTTP redirects as approved.
5. Responses include `X-Content-Type-Options: nosniff`,
   `X-Frame-Options: DENY`, and `Referrer-Policy: same-origin`.
6. A named evaluator can sign in, sees only authorized synthetic incidents, and
   receives an authorization failure for a synthetic incident outside their
   membership.
7. An approved revision can produce one synthetic export, and its digest can be
   checked with the [export verification procedure](export-verification.md).
8. The [audit-chain check](operation-and-monitoring.md#audit-chain-verification)
   passes.
9. A backup, checksum verification, and isolated restore drill pass under the
   [recovery runbook](backup-restore-and-rollback.md).
10. External map or reference data is absent unless its separate human approval
    and provenance record is complete.

If any check fails, leave external access disabled, preserve sanitized evidence,
and return the installation to the maintainer for review. Do not work around a
failed security, data, migration, or recovery gate.
