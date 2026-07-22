# TX-COMU test deployment

This procedure deploys the synthetic-data-only P1.0 prototype without changing the existing CiviCRM application. It uses this path:

`Internet -> edge Apache (10.1.5.250) -> toolkit frontend (10.1.5.251:8088) -> Django/PostGIS private network`

The deployment remains a test system. Do not enter operational, protected, sensitive, or personally identifiable information.

## Preconditions

- `ict-branch-toolkit.tx-comu.org` resolves to the edge server's public address.
- Back up the Apache configuration on the edge host before editing it.
- Install Docker Engine and the Compose plugin from Docker's supported Ubuntu repository on the application host.
- Permit TCP 8088 on the application host only from `10.1.5.250`.
- Obtain a trusted certificate for `ict-branch-toolkit.tx-comu.org` before enabling the HTTPS virtual host.

## Application host: 10.1.5.251

Clone the repository into a dedicated directory such as `/opt/ict-branch-toolkit`, check out an approved commit, and create a root-owned environment file that is readable only by root. Do not copy `.env.example` unchanged.

Required values:

```dotenv
POSTGRES_DB=ict_toolkit
POSTGRES_USER=ict_toolkit
POSTGRES_PASSWORD=<random database password>
DJANGO_SECRET_KEY=<random Django secret key>
DJANGO_SUPERUSER_USERNAME=<non-default administrator name>
DJANGO_SUPERUSER_EMAIL=<administrator email>
DJANGO_SUPERUSER_PASSWORD=<random initial administrator password>
VITE_MAP_STYLE_URL=
```

Start and verify the isolated stack:

```sh
docker compose --env-file /etc/ict-branch-toolkit.env -f compose.production.yaml config --quiet
docker compose --env-file /etc/ict-branch-toolkit.env -f compose.production.yaml up --build --detach --wait
curl --fail http://10.1.5.251:8088/api/health/
```

## Edge host: 10.1.5.250

Create `/etc/apache2/sites-available/ict-branch-toolkit.tx-comu.org-le-ssl.conf` after the certificate exists:

```apache
<VirtualHost *:443>
    ServerName ict-branch-toolkit.tx-comu.org

    SSLEngine on
    SSLCertificateFile /etc/letsencrypt/live/ict-branch-toolkit.tx-comu.org/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/ict-branch-toolkit.tx-comu.org/privkey.pem

    ProxyRequests Off
    ProxyPreserveHost On
    ProxyPass / http://10.1.5.251:8088/ connectiontimeout=5 timeout=60
    ProxyPassReverse / http://10.1.5.251:8088/

    RequestHeader set X-Forwarded-Proto "https"
    RequestHeader set X-Forwarded-Port "443"

    ErrorLog ${APACHE_LOG_DIR}/ict-branch-toolkit-error.log
    CustomLog ${APACHE_LOG_DIR}/ict-branch-toolkit-access.log combined
</VirtualHost>
```

Validate before reloading Apache:

```sh
apache2ctl configtest
systemctl reload apache2
curl --resolve ict-branch-toolkit.tx-comu.org:443:127.0.0.1 https://ict-branch-toolkit.tx-comu.org/api/health/
```

Do not change either existing CiviCRM virtual-host file. The dedicated SNI virtual host prevents the toolkit hostname from falling through to the CiviCRM default HTTPS site.

## Rollback

Disable only the toolkit virtual host and reload Apache. Then stop the toolkit Compose project without deleting its database volume:

```sh
a2dissite ict-branch-toolkit.tx-comu.org-le-ssl.conf
apache2ctl configtest
systemctl reload apache2

docker compose --env-file /etc/ict-branch-toolkit.env -f compose.production.yaml down
```

Do not add `--volumes` during rollback; that would delete the toolkit database.
