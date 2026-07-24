# Shared test deployment

This procedure deploys the synthetic-data-only P1.0 prototype as an isolated container stack behind an existing reverse proxy. It does not require or permit sharing another application's document root, database, or application process.

The deployment remains a test system. Do not enter operational, protected, sensitive, or personally identifiable information.

## Preconditions

- Back up the reverse-proxy configuration before editing it.
- Install Docker Engine and the Compose plugin from Docker's supported repository.
- Bind the published application port to an appropriate interface and permit access only from the reverse proxy.
- Obtain a trusted certificate for the deployment hostname before enabling its HTTPS virtual host.

## Application host

Clone the repository into a dedicated directory, check out an approved commit, and create a root-owned environment file that is readable only by root. Do not copy `.env.example` unchanged.

Required values:

```dotenv
POSTGRES_DB=ict_toolkit
POSTGRES_USER=ict_toolkit
POSTGRES_PASSWORD=<URL-safe random database password>
DJANGO_SECRET_KEY=<random Django secret key>
DJANGO_ALLOWED_HOSTS=<public hostname>,backend
DJANGO_CORS_ALLOWED_ORIGINS=https://<public hostname>
DJANGO_SUPERUSER_USERNAME=<non-default administrator name>
DJANGO_SUPERUSER_EMAIL=<administrator email>
DJANGO_SUPERUSER_PASSWORD=<random initial administrator password>
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
curl --fail http://<application-host>:8088/api/health/
```

## Controlled GitHub deployment

The `Deploy shared test` GitHub Actions workflow provides a manually dispatched
deployment path for the shared synthetic-data test host. Configure a protected
`shared-test` environment and require human review before the job can access its
repository secrets.

Required repository or environment secrets:

* `DEPLOY_HOST`
* `DEPLOY_PORT`
* `DEPLOY_USER`
* `DEPLOY_SSH_KEY`
* `DEPLOY_KNOWN_HOSTS`

The workflow accepts only the exact commit on `main`, refuses a dirty server
checkout, creates and validates a compressed PostgreSQL backup, builds new
images before replacing containers, and waits for all production health checks.
It must be started manually from the Actions tab ("Run workflow") and then
approved once at the `shared-test` environment gate; there is no separate
typed confirmation step. For this
synthetic-data-only shared test, the deployment script overlays the approved
public OSM configuration shown above into a restricted temporary environment
file. It does not rewrite the protected server environment file or expose its
secrets.

The `shared-test` environment requires human review before the job can run.
The job re-resolves `origin/main` immediately after that approval gate and
deploys that commit, not the commit that was current when the run was
dispatched, so an approval delay cannot by itself cause a mismatch. Even so,
**approve or reject a pending run within about 15 minutes of dispatch.** If a
run is left pending for hours, treat it as stale: reject it and re-dispatch
before approving, so the checked-out and validated commit stays close to the
one actually deployed. Merging to `main` while a run is awaiting approval is
still safe to do, but do so deliberately, and prefer re-dispatching after such
a merge rather than approving an older pending run against a moving target.

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

## Rollback

Disable only the application's virtual host and reload the reverse proxy. Then stop the Compose project without deleting its database volume:

```sh
docker compose --env-file /path/to/deployment.env -f compose.production.yaml down
```

Do not add `--volumes` during rollback; that would delete the application database.
