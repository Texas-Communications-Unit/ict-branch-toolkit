# Phase 1 Requirements and Acceptance Criteria

## Scope and limitations

Phase 1 is an operational-planning prototype. It must prove a controlled workflow from incident creation through approved exports without representing its output as a propagation study, coordination approval, spectrum authorization, or coverage guarantee. Only synthetic, public, or explicitly approved reference data may be used.

## P1.0 foundation

- **REQ-P10-001:** A new contributor can start the backend, PostGIS database, and frontend with Docker Compose. Acceptance: services become healthy and the API health response includes a PostGIS version.
- **REQ-P10-002:** An authenticated local administrator can create an incident and operational period. Acceptance: API tests demonstrate administrator success and reader/anonymous denial.
- **REQ-P10-003:** The frontend lists incidents obtained through the authenticated API. Acceptance: component and browser tests verify login and incident display.
- **REQ-P10-004:** A MapLibre map shell loads without a paid service or API key. Acceptance: the default inline style renders without a network map dependency.
- **REQ-P10-005:** Migrations, OpenAPI, formatting, linting, type checks, tests, builds, secret scanning, dependency review, and container builds run in CI.
- **REQ-P10-006:** Governance, security boundaries, data classification, architecture, data model, operations, and contributor workflow are documented.

## P1.1 accounts, incidents, and channel versions

- Implement configurable policy-backed Administrator, COML, COMC, COMT, Contributor, and Read-only roles.
- Complete incident and operational-period lifecycle with audit-preserving archival.
- Add separate, source-aware, versioned conventional-channel and trunked-talkgroup records.
- Provide validated administrator import with dry-run behavior and a small synthetic fixture.
- Gate: approve the NIFOG version, source, permitted use, and import method before full import.

## P1.2 ICS-205 revision control

- Model FEMA ICS-205 v3.1 structure, ordered assignments, continuation pages, copy-forward, validation, and revision comparison.
- Lock approved revisions and require a new draft for changes.
- Generate an initial deterministic FEMA-style PDF with render-based tests.
- Gate: qualified human review of ICS-205 semantics and final visual fidelity.

## P1.3 sites and manual rings

- Support site placement and decimal-degree, DMS, DDM, and USNG/MGRS entry.
- Associate sites and assignments many-to-many.
- Store WGS 84 coordinates and canonical meter distances.
- Render manual operational, fringe/uncertain, and coordination rings.
- Export approved site information as map output, KML, GeoJSON, and CSV.

## P1.4 explainable deconfliction

- Implement a versioned rule engine with stable rule IDs, severity, evidence, assumptions, and plain-language explanation.
- Detect co-channel, adjacent-channel, reversed input/output, duplicate-name/frequency, missing-value, and plan-omission conditions.
- Never suppress RF warnings solely because CTCSS, DCS, or NAC values differ.
- Gate: domain review by qualified incident communications and frequency-coordination practitioners.

## P1.5 export integrity

- Produce deterministic ICS-205 PDF, map, KML, GeoJSON, and CSV exports only from approved revisions.
- Stamp source incident, operational period, revision, approval state, generation time, and application version where appropriate.
- Prevent draft or post-approval changes from appearing as official.

## P1.6 hardening and release candidate

- Complete accessibility, error handling, backup/restore, audit review, security, performance, installation, upgrade, rollback, and operator documentation.
- Run dependency, secret, static-analysis, and container checks and publish tested limits.
- Produce a clearly labeled non-production release candidate and human acceptance checklist.

## Definition of done

Each milestone requires documented assumptions; reversible migrations; unit, integration, and updated end-to-end tests; passing format/lint/type/test/build/migration checks; security/privacy review; current documentation and sample configuration; approved data provenance; and a pull request describing changes, verification, limitations, screenshots, and follow-up work.

