# Security Model and Data Classification

## Classification

| Class | Examples | Public repository | Prototype environment |
| --- | --- | --- | --- |
| Public | Source code, public requirements, approved public reference metadata | Allowed | Allowed |
| Synthetic | Invented incidents, channels, sites, users, and credentials clearly marked for tests | Allowed | Allowed |
| Internal | Non-public planning notes, draft organizational configuration | Prohibited | Not approved in P1.0 |
| Protected/operational | Real incident data, protected channels, PII, credentials, keys, certificates, private infrastructure or connection details | Prohibited | Prohibited in P1.0 |

## Trust boundaries

The browser is untrusted. The backend enforces authentication, authorization, validation, and lifecycle rules. PostgreSQL/PostGIS is reachable only inside the Compose network by default. Map providers and future integrations are external systems and receive no operational data without an approved design and configuration.

## P1.0 controls

- Administrator-only mutation; authenticated reads.
- Token authentication for the local prototype; tokens are held in browser session storage and cleared when the session ends.
- Configuration through environment variables; `.env` is ignored.
- No required external map request or credential.
- Dependency, secret, static, test, and container checks in CI.
- Protective foreign keys and archival fields for operational records.

## Known risks and required hardening

P1.0 token authentication lacks production-grade expiration, rotation, revocation workflow, federation, and incident-scoped policy. Compose defaults are intentionally obvious development values. TLS termination, secure headers, backup encryption, audit completeness, rate limiting, upload controls, privacy retention, and production secrets management remain release blockers.

