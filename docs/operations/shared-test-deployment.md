# Live deployment

This procedure deploys the continuously improved ICT Branch Toolkit at
`toolkit.tx-comu.org` as an isolated container stack behind the existing reverse proxy.
It does not share another application's document root, database, or process.

The application provides planning decision support. It is not frequency coordination,
spectrum authorization, a propagation study, or a coverage guarantee. Protect incident,
personal, credential, and restricted channel information according to applicable policy.

## Preconditions

- Require the full pre-deployment Security workflow to pass for the exact candidate commit before protected environment approval. Follow the [security maintenance runbook](security-maintenance.md).
- Back up the reverse-proxy configuration before editing it.
- Install Docker Engine and the Compose plugin from Docker's supported repository.
- Bind the published application port to an appropriate interface and permit access only from the reverse proxy.
- Obtain a trusted certificate for the deployment hostname before enabling its HTTPS virtual host.

## Application host

Clone the repository into a dedicated directory, check out an approved commit,
and create a deployment-account-owned environment file with mode `0600`, readable
only by that account and root. Do not copy `.env.example` unchanged.

Required values:

```dotenv
POSTGRES_DB=ict_toolkit
POSTGRES_USER=ict_toolkit
POSTGRES_PASSWORD=<URL-safe random database password>
DJANGO_SECRET_KEY=<random Django secret key>
ICT_INVENTORY_ENCRYPTION_KEY=<URL-safe base64 encoding of 32 random bytes>
DJANGO_ALLOWED_HOSTS=<public hostname>,backend
DJANGO_CORS_ALLOWED_ORIGINS=https://<public hostname>
DJANGO_FORCE_HTTPS=true
DJANGO_HSTS_SECONDS=3600
DJANGO_THROTTLE_ANON_RATE=30/min
DJANGO_THROTTLE_USER_RATE=300/min
DJANGO_THROTTLE_AUTH_RATE=10/min
DJANGO_SUPERUSER_USERNAME=<non-default administrator name>
DJANGO_SUPERUSER_EMAIL=<administrator email>
DJANGO_SUPERUSER_PASSWORD=<random initial administrator password>
ICT_TOKEN_TTL_SECONDS=43200
ICT_PUBLIC_BASE_URL=https://toolkit.tx-comu.org
ICT_EMAIL_ENABLED=true
DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
DJANGO_EMAIL_HOST=smtp.dreamhost.com
DJANGO_EMAIL_PORT=587
DJANGO_EMAIL_USE_TLS=true
DJANGO_EMAIL_USE_SSL=false
DJANGO_EMAIL_HOST_USER=toolkit@tx-comu.org
DJANGO_EMAIL_HOST_PASSWORD=<SMTP password>
DJANGO_DEFAULT_FROM_EMAIL=ICT Branch Toolkit <toolkit@tx-comu.org>
DJANGO_PASSWORD_RESET_TIMEOUT_SECONDS=3600
APP_BIND_ADDRESS=<application-host address reachable by the reverse proxy>
APP_PORT=8088
VITE_MAP_STYLE_URL=
VITE_MAP_TILE_URL=
VITE_MAP_PROVIDER_ID=
VITE_MAP_PROVIDER_NAME=
VITE_MAP_ATTRIBUTION_TEXT=
VITE_MAP_ATTRIBUTION_URL=
VITE_MAP_LICENSE_NAME=
VITE_MAP_LICENSE_URL=
VITE_MAP_TERMS_URL=
VITE_MAP_PRIVACY_URL=
VITE_MAP_REPORT_ISSUE_URL=
VITE_MAP_CONTACT_URL=
```

The controlled deployment selects the U.S. Census MAF/TIGER address geocoder and
exactly allowlists USGS 3DEP EPQS for elevation and sampled terrain profiles. Both
are fixed, keyless federal public-service endpoints. Requests send the entered
address or coordinates to the named agency; review privacy and source limitations
before use.

Generate the inventory key on a trusted administrator workstation or the application host and
copy only the resulting value into the protected deployment environment file:

```bash
python -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```

Do not commit, email, or paste the key into an issue or pull request. Preserve it with the protected
database backup material. The application intentionally fails closed when accountable checkout is
used without a valid key.

`ICT_TOKEN_TTL_SECONDS` sets the maximum local login lifetime. The 12-hour default is the
non-production baseline. A shorter value is allowed after operator review; zero and negative values
prevent application startup. Changing the value can immediately expire existing sessions.

`ICT_PUBLIC_BASE_URL` is the verified public HTTPS origin used to construct account setup and
password-reset links. For this deployment it is `https://toolkit.tx-comu.org` (without a path).
Email recovery remains unavailable until valid SMTP settings are installed and tested; never commit
SMTP credentials to the repository.

The approved shared-test sender is `toolkit@tx-comu.org`, authenticated through DreamHost at
`smtp.dreamhost.com:587` using STARTTLS. The application does not use the mailbox's IMAP or POP3
settings. Store the mailbox password only in the protected deployment environment file.

`DJANGO_HSTS_SECONDS=3600` is a deliberately short initial test value. The
current application also emits the HSTS `includeSubDomains` and `preload`
directives when HTTPS enforcement is enabled. Increase the duration only after
the certificate, trusted-proxy header, affected host names, and rollback path
have passed maintainer review. Changing HSTS is a separate human-approved
configuration change.

The blank map-provider values are the secure default and render the neutral,
network-free map. After completing the
[map-provider deployment checklist](map-provider-deployment-checklist.md), a
maintainer may approve this limited synthetic-test configuration for the public
OSM standard raster service:

```dotenv
VITE_MAP_STYLE_URL=
VITE_MAP_TILE_URL=https://tile.openstreetmap.org/{z}/{x}/{y}.png
VITE_MAP_PROVIDER_ID=osm-standard
VITE_MAP_PROVIDER_NAME=OpenStreetMap standard tiles
VITE_MAP_ATTRIBUTION_TEXT=© OpenStreetMap contributors
VITE_MAP_ATTRIBUTION_URL=https://www.openstreetmap.org/copyright
VITE_MAP_LICENSE_NAME=Open Database License 1.0
VITE_MAP_LICENSE_URL=https://opendatacommons.org/licenses/odbl/1-0/
VITE_MAP_TERMS_URL=https://operations.osmfoundation.org/policies/tiles/
VITE_MAP_PRIVACY_URL=https://osmfoundation.org/wiki/Privacy_Policy
VITE_MAP_REPORT_ISSUE_URL=https://www.openstreetmap.org/fixthemap
VITE_MAP_CONTACT_URL=https://github.com/Texas-Communications-Unit/ict-branch-toolkit/issues
```

This test configuration is not approved for protected, confidential, personal,
or operational location data. It does not permit bulk downloads, prefetching,
automated map browsing, offline packages, or public Nominatim geocoding.

Start and verify the isolated stack:

```sh
docker compose --env-file /path/to/deployment.env -f compose.production.yaml config --quiet
docker compose --env-file /path/to/deployment.env -f compose.production.yaml up --build --detach --wait
application_host=127.0.0.1
public_hostname=toolkit.example.invalid
curl --fail \
  --header "Host: $public_hostname" \
  --header 'X-Forwarded-Proto: https' \
  "http://$application_host:8088/api/health/"
```

The forwarded-protocol header is valid only because the application listener is
restricted to the trusted reverse proxy or administrator. Do not expose a
listener that trusts this header to an untrusted network.

## Controlled GitHub deployment

The `Deploy to Server` GitHub Actions workflow runs the full reusable Security
workflow on pushes to `main` and can also be dispatched manually from `main`.
Manual runs default to `verify`, which checks Azure authentication and the
deployment account without updating the application. Select `deploy` explicitly
for a manual upgrade; push-triggered runs retain the approved deployment path.
Every applicable security and regression check must succeed before the deployment
job requests approval. Configure a protected
`shared-test` environment and require human review before the job can access its
repository secrets.

Required `shared-test` environment secrets:

- `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`
- `AZURE_RESOURCE_GROUP`, `AZURE_VM_NAME`
- `DEPLOY_USER` (the existing dedicated Linux deployment account)

Azure OIDC authenticates the job after approval. Managed Run Command delivers
the exact scanned deployment helpers to the VM agent, which switches to the
deployment account. Public SSH access from Actions is not required. See
[Azure identity setup and verification](azure-deployment-identity.md).
The old `DEPLOY_HOST`, `DEPLOY_PORT`, `DEPLOY_SSH_KEY`, and
`DEPLOY_KNOWN_HOSTS` secrets are no longer read by this workflow. Retain the old
credentials privately until both Azure deployment and FCC synchronization have
passed verification, then revoke the obsolete key and remove unused secrets as
a separate administrator action. Follow the
[FCC migration and key-retirement procedure](azure-fcc-synchronization.md);
`DEPLOY_USER` remains required. The former server-connected capacity Actions
workflow is retired; use only an isolated synthetic host for capacity tests.

The workflow accepts only the exact commit on `main`, refuses a dirty server
checkout, creates a matched PostgreSQL, attachment, and protected-configuration
recovery set, builds new images before replacing containers, and waits for all
production health checks. The job allows 60 minutes. Both push-triggered and
manually dispatched jobs must be approved at the `shared-test` environment gate;
there is no separate typed confirmation step. For this
live system, the deployment script overlays the approved public OSM, Census,
USGS 3DEP, CISA NIFOG, and FCC-supporting configuration into a restricted temporary
environment file. It does not
rewrite the protected server environment file or expose its secrets.

Before approving an upgrade, follow the
[backup, restore, upgrade, and rollback runbook](backup-restore-and-rollback.md)
to run an isolated restore drill. The controlled deployment writes a SHA-256
sidecar for its pre-deployment backup, but the backup and checksum must still be
copied to approved encrypted storage outside the application host.

### Consistent upgrade backups and maintenance

Approve a maintenance window before releasing a deployment. The recovery helper
stops the frontend and backend while keeping PostgreSQL running, creates and
validates the database dump and attachment archive, and privately saves the
original protected deployment environment before candidate provider overlays.
Restore this file with the recorded source commit to reconstruct the prior
deployment's approved overlays. This can take several minutes for large
reference databases; the pause lasts for the full backup, not only the image swap.
Prevent user changes for the entire approved upgrade window, including the build
and post-upgrade verification interval; a recovery point precedes those later
writes. The original containers are resumed before builds start, including after ordinary
backup failures or SIGTERM/SIGINT. A failed resume fails the deployment and needs
operator intervention. A forced kill, host failure, or lost remote process must
be followed by an explicit service-health check; no shell trap can guarantee
recovery from SIGKILL.

The final `.recovery.json` marker records the source and target commits and the
three matched files. Each file has a SHA-256 sidecar. No code promotion occurs
unless backup validation and application resumption succeed. Keep the environment
copy private: it contains credentials and the inventory encryption key. Never
upload recovery-set contents as public Actions artifacts. Retention removes
the matching attachment/configuration companions only for verified complete sets;
corrupt or incomplete companions require operator review. Restore the matching
attachments and configuration alongside the database using the recovery runbook.

Deployment and scheduled FCC synchronization share a host maintenance lock under
the deployment account. A conflicting operation exits before writing and must be
retried; this does not create an unbounded queue or bypass approval.

### Azure host preparation

Use a dedicated deployment account. Its home must
contain `apps/ict-branch-toolkit`, the protected
`.config/ict-branch-toolkit/deployment.env`, and `backups/ict-branch-toolkit`.
Keep backups on the managed data disk through a directory or symlink. Configure
Docker's `data-root` on the persistent data disk and a systemd `RequiresMountsFor`
dependency so a missing disk cannot initialize an empty replacement database.
Docker access is root-equivalent and must be limited to trusted deployment identities.
When Apache and the application run on the same VM, use
`APP_BIND_ADDRESS=127.0.0.1` and `APP_PORT=8088`. Do not publish the application,
backend, or database ports to the Internet; expose HTTP/HTTPS and approved SSH only.

The frontend must send a valid Referer to the approved public OSM service. For
Apache, use `Referrer-Policy: strict-origin-when-cross-origin` on frontend responses
and retain `same-origin` for `/api/`. This exposes only the public origin on
external HTTPS requests, not incident paths or query strings. A blanket frontend
`same-origin` policy suppresses OSM identification and can produce blocked tiles.
Check the live frontend policy, API health, and an operator-viewed map after a
proxy change. Do not automate map browsing, tile prefetching, or cache bypass.

Keep server addresses, private keys, credentials, certificates, and recovery data
out of the repository. Store the Azure connection values in environment secrets and
preserve existing application/database/encryption secrets on the server during
retargeting. Verify federated identity and a harmless Azure Run Command before
the first deployment. Keep SSH restricted to approved administrator addresses.

The `shared-test` environment requires human review before the deployment job
can run. The job checks out the exact SHA already scanned and compares it with
`origin/main` after approval. If main has advanced, deployment refuses to proceed;
it never substitutes a newer, unscanned commit. Reject stale pending runs and
re-dispatch from current main, which runs the full checks again before approval.

## Reverse proxy

Create a dedicated HTTPS virtual host for the application hostname. Preserve the original host, pass the original HTTPS scheme, and proxy only to the application's dedicated address and port.

```apache
<VirtualHost *:443>
    ServerName <public-hostname>

    SSLEngine on
    SSLCertificateFile /path/to/fullchain.pem
    SSLCertificateKeyFile /path/to/privkey.pem

    ProxyRequests Off
    ProxyPreserveHost On
    ProxyPass / http://<application-host>:8088/ connectiontimeout=5 timeout=60
    ProxyPassReverse / http://<application-host>:8088/

    RequestHeader set X-Forwarded-Proto "https"
    RequestHeader set X-Forwarded-Port "443"
</VirtualHost>
```

Validate before reloading the reverse proxy. Confirm the health endpoint through the public hostname before allowing test use.

Complete the
[installation verification](installation-and-configuration.md#installation-verification)
and adopt the
[operation and monitoring runbook](operation-and-monitoring.md) before opening
the synthetic test to evaluators.

## Rollback

For an application or database migration rollback, use the guarded procedure in
the [recovery runbook](backup-restore-and-rollback.md). Disable only the
application's virtual host and reload the reverse proxy before recovery. To stop
the Compose project without deleting its database volume:

```sh
docker compose --env-file /path/to/deployment.env -f compose.production.yaml down
```

Do not add `--volumes` during rollback; that would delete the application database.
