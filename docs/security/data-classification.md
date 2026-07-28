# Security Model and Data Classification

## Classification

| Class                 | Examples                                                                                                                   | Public repository | Prototype environment |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------- | ----------------- | --------------------- |
| Public                | Source code, public requirements, approved public reference metadata                                                       | Allowed           | Allowed               |
| Synthetic             | Invented incidents, channels, sites, users, and credentials clearly marked for tests                                       | Allowed           | Allowed               |
| Internal              | Non-public planning notes, draft organizational configuration                                                              | Prohibited        | Not approved in P1.0  |
| Protected/operational | Real incident data, protected channels, PII, credentials, keys, certificates, private infrastructure or connection details | Prohibited        | Prohibited in P1.0    |

## Trust boundaries

The browser is untrusted. The backend enforces authentication, authorization, validation, and lifecycle rules. PostgreSQL/PostGIS is reachable only inside the Compose network by default. Map providers and future integrations are external systems and receive no operational data without an approved design and configuration.

## Phase 2 RF input classification

RF analysis inputs, subscriber profiles, RF input snapshots, notes, and digests inherit the
highest classification of their incident and source material. A digest is an integrity identifier,
not anonymization or encryption.

Real equipment capabilities, receiver thresholds, antenna configuration, mounting, site heights,
losses, gains, and terrain methods may reveal operational capability or infrastructure even when
they contain no personal information. They therefore remain prohibited in the prototype unless
the exact data is explicitly approved under a later data-classification decision. Issue #15
documentation, fixtures, screenshots, tests, and review evidence use synthetic values only.

Data minimization excludes equipment serial numbers, asset identifiers, owner contacts,
credentials, protected channel details, private host information, and unrelated incident
narrative. Version-level `input_basis` and minimal notes distinguish recorded facts from modeled
assumptions without copying sensitive source records into the application. Approved snapshots
retain minimized profile identity/description, version identity, canonical RF values, basis and
notes, the calculation path, digest, and approval metadata needed to reproduce the later
decision-support input selection.

Elevation queries, cached samples, provider metadata, HAAT results, and their snapshots inherit
the incident and source-material classification. Coordinates and terrain-derived site heights may
identify infrastructure even when names are minimized. They are protected application records,
not public telemetry. The browser cannot select an arbitrary provider or remote URL. Audit detail
does not duplicate coordinates or sample values.

Only deterministic synthetic terrain is committed to the repository. A real elevation dataset or
cache may not be committed, exported, or redistributed until its exact permitted use, attribution,
retention, and redistribution terms are approved. SHA-256 digests identify retained content; they
do not anonymize the source or incident.

## RadioReference boundary

The public repository may contain only the disabled adapter contract and
obviously synthetic RadioReference-shaped fixtures. The developer key,
individual-user credentials, authentication responses, real source data, raw
SOAP/XML, normalized live records, caches, screenshots, exports, and derived
datasets are prohibited.

Future RadioReference data inherits the strictest incident, source, credential,
and licensing classification. A source identifier, response digest, or
normalization step does not make provider data public or authorize retention.
Live access requires the separate licensing and security gate in the
[provider procedure](../operations/radioreference-provider.md).

Field observations and calibration evidence inherit the highest classification of their incident,
RF input, analysis source, observer/source, location, time, measurements, notes, and collection
authority. Generalization reduces coordinate precision but is not anonymization; redaction is the
only current mode that retains no coordinate. Repeated time/location/path records can still reveal
people, sites, equipment behavior, or operational capability.

Observation review and calibration snapshots minimize derived evidence but do not declassify it.
Digests remain identifiers, not confidentiality controls. The public repository and Actions
fixtures use synthetic observers, locations, measurements, source identifiers, and notes only.
Real field evidence, screenshots, exports, database backups, or support material require an
approved classification, access, retention, disclosure, and destruction plan.

Phase 2 validation bundles inherit the strictest classification of the
incident, plan, RF inputs, sites, terrain, observations, and calibration
evidence. The controlled export omits plan contacts and remarks plus
observation coordinates, observer/source text, and notes, but minimization does
not declassify the remaining infrastructure, capability, actor, time, or digest
evidence. Exports and backups remain protected application records unless an
explicit authority determines otherwise.

## Current prototype controls

- Centralized backend policy for installation and incident-scoped roles.
- Bounded local-token authentication; tokens rotate at sign-in, can be revoked
  at sign-out, and are held only in browser session storage until sign-out,
  expiry, an authentication failure, or the browser session ends.
- Configuration through environment variables; `.env` is ignored.
- No required external map request or credential.
- Optional external basemaps fail closed unless endpoint, attribution, license,
  terms, privacy, issue-reporting, and support metadata are complete. Enabling
  one discloses the viewed geographic area to that provider and remains
  synthetic-test-only until a separate operational privacy determination.
- Dependency, secret, static, test, and container checks in CI.
- Secure response headers, configurable HTTPS/HSTS behavior, general API rate
  limits, and a stricter authentication rate limit.
- Generic server-error responses that do not disclose exception detail.
- Guarded database backup, checksum verification, isolated restore drills,
  controlled restoration, and application/migration rollback procedures.
- Append-only audit events with an internally verifiable hash chain.
- Protective foreign keys and archival fields for operational records.

## Known risks and required hardening

Local tokens are bounded and revocable but remain bearer credentials without
self-service recovery, multifactor authentication, or approved federation.
Compose development defaults are intentionally obvious values and must never be
used on a shared system. TLS termination, secret management, backup encryption
and retention, certificate monitoring, external audit anchoring, privacy
retention, provider governance, and operational alerting remain
installation-owner controls. Tested capacity is limited to the published
prototype performance evidence. These limitations must be resolved or
explicitly accepted for a non-production candidate and still do not establish
production readiness.
