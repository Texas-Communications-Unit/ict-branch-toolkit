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
```

Start and verify the isolated stack:

```sh
docker compose --env-file /path/to/deployment.env -f compose.production.yaml config --quiet
docker compose --env-file /path/to/deployment.env -f compose.production.yaml up --build --detach --wait
curl --fail http://<application-host>:8088/api/health/
```

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
