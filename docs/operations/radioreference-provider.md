# RadioReference provider safety boundary

## Current operating state

The RadioReference integration is a **disabled synthetic contract**, not a live
provider. It makes no external request and does not support developer keys,
individual-user credentials, cache, import, or export. Setting
`RADIOREFERENCE_ENABLED=true` does not change those restrictions.

Use the current RadioReference service and account documentation only as a
starting point for the required written licensing review:

- [Database Web Service API](https://support.radioreference.com/hc/en-us/articles/18844460198932-Database-Web-Service-API)
- [Programming Using the RadioReference Web Service](https://support.radioreference.com/hc/en-us/articles/18860633200276-Programming-Using-the-RadioReference-Web-Service)
- [RadioReference API account page](https://www.radioreference.com/account/api)
- [Current WSDL](https://api.radioreference.com/soap2/?wsdl&v=latest)

An approved developer application is not, by itself, approval for multiuser
governmental/nonprofit planning, storage, display, printing, offline use, or
redistribution.

## Safe configuration

Keep these values in the protected server-side deployment environment:

```dotenv
RADIOREFERENCE_ENABLED=false
RADIOREFERENCE_WSDL_URL=https://api.radioreference.com/soap2/?wsdl&v=latest
RADIOREFERENCE_MAX_RESPONSE_BYTES=1048576
```

- The URL must use HTTPS and cannot embed credentials or a fragment.
- The response limit must be 1,024 through 5,242,880 bytes.
- Do not add the developer key or an end-user username/password to the
  repository, frontend environment, image build arguments, test fixtures,
  screenshots, logs, command-line arguments, or issue/PR text.
- Do not provision `RADIOREFERENCE_API_KEY` to a shared host while the live
  transport and credential exchange remain unimplemented.

## Verification

An authenticated administrator may inspect:

```sh
curl \
  --header "Authorization: Token REDACTED" \
  https://toolkit.example.invalid/api/radioreference-provider/
```

The response must report:

- `mode: "disabled"` and `available: false`;
- `synthetic_contract_available: true`;
- `live_transport_implemented: false`;
- `developer_key_loaded: false`;
- `user_credentials_supported: false`;
- `credentials_retained: false`; and
- cache, import, and export support as `false`.

Run the contract tests without any external credentials:

```sh
cd backend
pytest -q tests/test_radioreference_provider.py
python manage.py makemigrations --check --dry-run
python manage.py spectacular --file openapi.yaml --validate
```

The tests accept only an explicitly synthetic namespace, source version, source
identifiers, and retrieval scope. They verify response-size bounds, SOAP shape,
DTD/entity rejection, field allowlists, numeric limits, provenance, and
non-retention.

## Required live-enablement review

Do not implement or enable live traffic until written terms and maintainers
approve every item below:

1. intended governmental/nonprofit incident-planning and multiuser use;
2. individual Premium-account authentication and subscription-failure behavior;
3. query, field, rate, retention, cache, derived-work, display, controlled export,
   offline, redistribution, attribution, deletion, and termination limits;
4. short-lived credential handling, disconnect/revocation, rotation, redacted
   errors, incident response, and administrative kill switch;
5. outbound endpoint allowlisting, bounded timeouts/retries, XML hardening, and
   health monitoring;
6. review/diff, provenance, versioned import, and audit behavior; and
7. the exact shared or production environment.

The next implementation must remain replaceable and server-side. It must not
expose SOAP/XML or credentials to the browser, silently overwrite local
libraries, or treat provider data as an operational assignment.

## Disablement and incident response

The current build is already disabled. If future live work is approved, its
runbook must make `RADIOREFERENCE_ENABLED=false` an immediate kill switch that
does not interrupt local Toolkit operation. On suspected credential or data
exposure, disable the provider, revoke affected user sessions, rotate the
developer key through the approved owner, preserve sanitized audit evidence, and
follow the written deletion and notification obligations.
