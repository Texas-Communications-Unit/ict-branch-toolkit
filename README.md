# ICT Branch Toolkit

ICT Branch Toolkit is an open-source web application for incident communications planning, radio-site mapping, coverage visualization, and frequency deconfliction. It is intended to support Communications Unit and Information and Communications Technology (ICT) Branch personnel during incidents, planned events, exercises, and pre-incident planning.

> **Project status:** Phase 1 non-production prototype. No production-ready
> release is available, and the application must use synthetic data only. Any
> candidate must follow the
> [non-production release-candidate process](docs/releases/non-production-release-candidate.md).

## Vision

ICT Branch Toolkit will bring the incident radio plan, channel library, radio sites, and geographic analysis into one controlled workspace. The goal is a fast, explainable planning tool that helps users build the plan, see the system, identify potential conflicts, and publish approved information without depending on a proprietary platform.

The application will be independently deployable. The first hosted implementation is planned for the [Texas Communications Unit (TX-COMU)](https://tx-comu.org), but other organizations will be able to operate and brand their own installations.

## Planned capabilities

### ICS-205 development

- Build and revise an Incident Radio Communications Plan through a web interface.
- Follow the current [FEMA ICS-205 v3.1](https://training.fema.gov/emiweb/is/icsresource/assets/ics%20forms/ics%20form%20205%2C%20incident%20radio%20communications%20plan%20%28v3.1%29.pdf) structure.
- Manage incidents and operational periods.
- Select conventional channels and trunked-system talkgroups from controlled libraries.
- Add agency, regional, or incident-specific resources that are not part of the NIFOG.
- Copy assignments forward, reorder rows, and generate continuation pages.
- Lock published plans and preserve revisions, approvals, and audit history.
- Export an official FEMA-style ICS-205 PDF.

### Channel library

- Maintain a protected, versioned reference library based on the current [CISA National Interoperability Field Operations Guide (NIFOG)](https://www.cisa.gov/resources-tools/resources/nifog).
- Preserve the source and version used by each published incident plan.
- Keep authoritative reference records separate from local and incident-created resources.
- Store conventional frequencies and trunked talkgroups as distinct resource types.
- Record RX/TX frequencies, bandwidth, mode, tones or NACs, restrictions, authorization notes, and source details.

### Radio-site mapping

- Place sites by map click, draggable pin, address, or coordinate entry.
- Support decimal degrees, degrees/minutes/seconds, degrees and decimal minutes, and USNG/MGRS.
- Associate one site with multiple ICS-205 assignments and one assignment with multiple sites.
- Track repeaters, bases, gateways, caches, receive-only locations, dispatch points, and other configurable site types.
- Display expected operational, fringe or uncertain, and coordination/interference areas.
- Distinguish talk-out, talk-in, and probable two-way operational coverage.
- Export site and coverage information as maps, KML, GeoJSON, and CSV.

### Deconfliction

- Identify possible co-channel and adjacent-channel conflicts where operating or coordination areas overlap.
- Consider frequency relationships, geographic overlap, and simultaneous operation.
- Detect reversed repeater input/output frequencies, duplicate frequencies under different names, missing technical values, and active resources not listed on the approved ICS-205.
- Explain why each condition was flagged instead of returning only a severity color.
- Display CTCSS, DCS, and NAC values without treating different squelch values as protection from RF interference.

### Workflow and access

The permission model is expected to support COML, COMC, COMT, administrator, contributor, and read-only roles while allowing organizations to configure authority for their own operations. Draft data will remain separate from approved and published information.

## Development roadmap

### Phase 1 — Operational planning prototype

- Incident and operational-period records
- Versioned channel library
- Web-based ICS-205 editor
- NIFOG, local, and incident-created resources
- Map-based site placement and coordinate conversion
- Manual coverage and coordination rings
- Basic co-channel and adjacent-channel warnings
- ICS-205, map, KML, GeoJSON, and CSV exports
- Revision history and approval lock

### Phase 2 — Calculated estimates and field calibration

- Versioned transmitter, receiver, antenna, feed-line, ERP, AGL, AMSL, HAAT,
  and subscriber-profile inputs
- Explicit recorded-fact, modeled-assumption, mixed, and unknown input basis
- Explainable coverage estimates by band and operating environment
- Talk-in and talk-out analysis
- Automatic elevation and HAAT support
- Field observations for good, marginal, and failed communications
- Confidence ratings and locally calibrated presets

### Phase 3 — Advanced operations

- Optional terrain-aware analysis
- Offline and intermittent-connectivity operation
- Multiuser incident collaboration
- Additional ICT Branch planning tools and reports
- Static TAK data packages and an authorized live TAK connector

Future TAK support will be implemented through a replaceable interface. No agency credentials, certificates, private server details, or operational connection information will be included in the public repository.

## Architecture principles

- **Standalone:** The application will not depend on WordPress, CiviCRM, or the TX-COMU website.
- **Portable:** Branding, authentication, map sources, channel libraries, and external integrations will be configurable.
- **Source-aware:** Reference data will retain its source, version, and effective status.
- **Operationally controlled:** Only approved information will be eligible for official exports or future TAK publication.
- **Explainable:** Coverage estimates and conflict warnings will show the assumptions and rules that produced them.
- **Secure by default:** Secrets, certificates, database dumps, uploads, and operational incident data must remain outside source control.
- **Open source:** The project will be developed in public for reuse and improvement by the incident communications community.

The P1.0 baseline is Django/GeoDjango and Django REST Framework, PostgreSQL/PostGIS, React/TypeScript/Vite, MapLibre GL JS, and Docker Compose. The decision and its boundaries are recorded in [ADR-0001](docs/adr/0001-application-architecture.md).

## P1.0 quick start

Prerequisites: Git, Docker Engine with Compose v2, and at least 4 GB of memory available to Docker.

```sh
cp .env.example .env
docker compose up --build
```

Open <http://localhost:5173>. The local administrator credentials come from `.env`. Change the example password before use, even in a shared development environment.

The backend API is at <http://localhost:8000/api/>, its OpenAPI UI is at <http://localhost:8000/api/docs/>, and the health endpoint is at <http://localhost:8000/api/health/>. A healthy PostgreSQL-backed response includes the detected PostGIS version.

### Verification

```sh
make check
docker compose config --quiet
docker compose up --build --wait
curl http://localhost:8000/api/health/
```

Without `make`, run the commands defined in the Makefile individually. Reset the local development database with `make reset`; this deletes only the Compose volume for this project and must not be used against an operational database.

### Local non-container checks

Backend tests intentionally support SQLite so contributors can run unit/API tests without PostGIS. Docker and CI remain authoritative for the PostGIS integration path.

```sh
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
pytest
python manage.py makemigrations --check --dry-run
python manage.py spectacular --file openapi.yaml --validate

cd ../frontend
corepack enable
pnpm install --frozen-lockfile
pnpm lint
pnpm typecheck
pnpm exec vitest run
pnpm build
pnpm exec playwright install chromium
pnpm test:e2e
```

Windows PowerShell uses `.venv\Scripts\Activate.ps1` for virtual-environment activation.

### Shared test deployment

The shared synthetic-data test deployment uses a separate production Compose definition, a single configurable frontend port, and an external reverse proxy. Follow [the shared test deployment runbook](docs/operations/shared-test-deployment.md). It intentionally does not modify or share another application's database or document root.

Database backups, isolated restore drills, controlled restoration, upgrades,
and application or migration rollback follow the
[recovery runbook](docs/operations/backup-restore-and-rollback.md).
The current hardware-neutral API regression envelopes and their deliberately
limited non-production scope are published in
[tested performance limits](docs/operations/performance-tested-limits.md).

### Operations and release evaluation

Use the
[installation and configuration guide](docs/operations/installation-and-configuration.md)
for a reviewed evaluation build and the
[operation and monitoring runbook](docs/operations/operation-and-monitoring.md)
for routine health, logging, backup, audit-chain, access, and escalation checks.
The
[release-candidate process and checklist](docs/releases/non-production-release-candidate.md)
defines the artifacts, evidence, immutable candidate identity, and human
approvals required before a clearly labeled non-production prototype
prerelease. It does not authorize a tag, release, deployment, or non-synthetic
data by itself.

## P1.1 vertical slice

The current slice provides bounded, rotating token-based local authentication with server-backed
sign-out; centralized Administrator, COML, COMC, COMT, Contributor, and Read-only policy defaults;
incident memberships; audit-preserving archival; append-only API audit events; and separate
source-versioned conventional-channel and trunked-talkgroup libraries. Administrators can validate
an import without writing data and apply an atomic approved import. CISA reference releases remain
blocked from application until their exact type, version, authoritative URL, and digest pass the
configured human gate.

The browser workspace consumes backend capabilities, displays library provenance, and provides an
administrator-only validation/import panel using a clearly synthetic example. See
[reference import operations](docs/operations/reference-library-imports.md),
[account and audit controls](docs/security/accounts-and-audit.md),
[ADR-0002](docs/adr/0002-identity-authorization-and-audit.md), and
[ADR-0007](docs/adr/0007-local-token-lifecycle.md).

## P1.2 ICS-205 vertical slice

The current branch adds incident/operational-period plans, numbered drafts, ordered assignment rows, controlled resource snapshots, Remote Base/Link/Patch relationships, optional protected contact details, revision comparison, approval locking, copy-forward, and a deterministic approved-only PDF. Backend permissions and audit records control every material action.

The PDF is an initial FEMA-style planning output. Qualified practitioners must validate ICS-205 semantics, and maintainers must visually approve final form fidelity. Contact fields are not exported. Canonical site coordinates arrive in P1.3 rather than being duplicated on a row.

## P1.3 spatial planning vertical slice

The toolkit now stores incident-scoped WGS 84 radio sites, accepts decimal-degree, DDM, DMS, and USNG/MGRS coordinates, supports map clicks and draggable MapLibre pins, and renders operator-entered operational, fringe/uncertain, and coordination rings stored canonically in meters. Sites associate many-to-many with ICS-205 assignments.

Plan approval freezes each associated site's coordinate provenance, source identity, and rings. Approved-only SVG map, KML, GeoJSON, and CSV exports read those snapshots, so later canonical site edits cannot silently rewrite an official output. The neutral map and coordinate workflow remain usable without a network connection, paid provider, or API key. The replaceable address-provider hook is disabled by default.

External basemaps are disabled by default and fail closed unless their endpoint,
provider identity, attribution, license, terms, privacy, issue-reporting, and
support metadata are complete. See
[Open mapping compliance](docs/governance/open-mapping-compliance.md) and the
[map-provider deployment checklist](docs/operations/map-provider-deployment-checklist.md).

See [ADR-0004](docs/adr/0004-spatial-sites-snapshots-and-exports.md) and [spatial input and reference-source controls](docs/operations/spatial-inputs-and-reference-sources.md).

The prototype does not yet implement production identity controls such as multifactor
authentication and approved external federation.

## P2.1 versioned RF input design

Issue #15 implements incident-scoped and versioned RF analysis inputs through portable, mobile,
fixed, cache, gateway, or configurable subscriber profiles. The workflow is:

1. create an incident-scoped subscriber profile and its first numbered draft;
2. record typed transmitter, receiver, antenna, feed-line, gain/loss, polarization, band,
   emission, mounting, and AGL/AMSL/HAAT values;
3. leave unavailable nullable values as `null` and controlled values as `unknown` rather than
   substituting zero or a default;
4. label the complete version as `recorded_fact`, `modeled_assumption`, `mixed`, or `unknown`, and
   use non-sensitive notes to explain mixed inputs;
5. record ERP as unknown, entered with non-sensitive source/method notes, or server-calculated,
   preserving the versioned transmitter-power-to-antenna-input-to-ERP calculation path;
6. approve and lock the exact profile version, canonical input snapshot, digest, actor, and time;
   and
7. create an immutable named `RFAnalysisInputSnapshot` from the approved version for later
   analysis use.

Approved profile versions and RF input snapshots are immutable; profile changes create new
drafts. All numerical ranges, cross-field tolerances, calculation conventions, and subscriber
assumptions are provisional. **No operational default is approved.** Qualified COML, COMT, COMC,
and RF engineering practitioners must complete the human gate before the design is treated as
operationally suitable. Only synthetic or explicitly approved data may be used.

See the [Phase 2 RF input data model](docs/data-model/phase-2.md) and
[ADR-0008](docs/adr/0008-versioned-rf-analysis-inputs-and-subscriber-profiles.md). P2.2 binds
HAAT results to these snapshots; calculated propagation results remain outside P2.1. Any later
output remains planning decision support, not a propagation study, frequency-coordination
approval, spectrum authorization, or coverage guarantee.

## P2.2 source-aware elevation and HAAT

Issue #16 adds a server-selected, replaceable elevation-provider boundary, immutable elevation
cache snapshots, and retained HAAT calculations. External terrain is disabled by default and no
third-party terrain is bundled. A configured provider is called only when its complete source
descriptor is present in the server approval allowlist.

The calculation binds to an immutable approved RF input snapshot and records site and
profile-version inputs, provider/product provenance, horizontal and vertical references,
transformation, coverage and license metadata, every radial/azimuth and distance parameter, sample
exclusions, rounding, warnings, and SHA-256 digests. Complete results may be approved and locked;
partial and unavailable results remain visible but cannot be approved. Retry creates new source
and result records instead of rewriting prior evidence.

The bundled deterministic provider is synthetic and offline-only. It supports automated flat,
sloped, rugged, missing-data, boundary, out-of-coverage, and datum-conversion fixtures. It is not
actual terrain and must never be used for operational decisions.

See [ADR-0009](docs/adr/0009-source-aware-elevation-and-reproducible-haat.md) and the
[elevation/HAAT operations guide](docs/operations/elevation-and-haat.md). The method is a
provisional general planning radial-average terrain method, not a claim that any one regulatory
service's HAAT method governs all land-mobile-radio work.

## P2.3 explainable band and environment estimates

Issue #17 adds a replaceable server-side estimate-engine interface and an immutable
`CoverageEstimate` workflow. The initial `fspl-horizon-v1-provisional` implementation consumes
only a complete approved HAAT calculation and its exact approved RF input snapshot. It preserves
the site coordinates, source digests, engine and preset versions, formulas, constants,
intermediate values, limiting factors, warnings, explanation, conservative/nominal/optimistic
distances, deterministic WGS 84 geometry, and result digest.

Manual Phase 1 rings remain separate. Calculated nominal geometry uses a dashed map layer and the
same results, assumptions, warnings, and digests appear in an accessible table. Unsupported bands
or inputs create explicit retained results without invented geometry.

The shipped band groups, environment margins, receiver-height assumption, uncertainty, distance
limits, rounding, and formulas are synthetic-evaluation defaults that have not passed the
qualified practitioner gate. They are not operational defaults. See
[ADR-0010](docs/adr/0010-provisional-explainable-coverage-estimates.md), the
[coverage-estimate operations guide](docs/operations/coverage-estimates.md), and the
[Phase 2 data model](docs/data-model/phase-2.md).

## P2.4 separate talk-out, talk-in, and probable two-way analysis

Issue #18 adds immutable directional analysis using one complete approved infrastructure HAAT
result and a distinct approved subscriber RF snapshot. Infrastructure-to-subscriber talk-out and
subscriber-to-infrastructure talk-in use their applicable transmit ERP and receiver sensitivity.
The provisional `concentric-minimum-v1-provisional` rule derives probable two-way distance only
from the smaller supported nominal path and identifies the limiting direction.

Portable, mobile, fixed, cache, gateway, and configurable profiles remain versioned assumption
sets rather than measured equipment facts. Frequency mismatches, incomplete paths, and unsupported
inputs remain explicit and produce no fabricated two-way geometry. Directional layers, P2.3
single-path estimates, and manual rings remain separate in the API, accessible tables, and map.

Approval fails closed until the exact engine, preset, and directional rule pass qualified review.
See [ADR-0011](docs/adr/0011-separate-directional-and-two-way-analysis.md), the
[directional analysis operations guide](docs/operations/directional-coverage-analysis.md), and the
[Phase 2 data model](docs/data-model/phase-2.md).

## Optional RadioReference synthetic contract

Issue #33 adds only a disabled, server-side synthetic contract for future
RadioReference evaluation. It normalizes obviously synthetic agency, frequency,
trunked-system, site, and talkgroup XML while enforcing response-size, SOAP
shape, DTD/entity, field, numeric, provenance, and non-retention controls.

There is no live transport, developer-key loading, user-credential handling,
cache, import, or export. `RADIOREFERENCE_ENABLED=true` records intent but still
reports the provider unavailable. Live work remains blocked pending written
licensing clarification, an individual Premium-account security design, secret
provisioning, and maintainer approval. See
[ADR-0014](docs/adr/0014-disabled-radioreference-provider-contract.md) and the
[RadioReference safety boundary](docs/operations/radioreference-provider.md).

## P2.5 field observations and controlled local calibration

Issue #19 records immutable, incident-scoped good, marginal, and failed-communications
observations tied to exact approved RF input snapshots and optional approved analysis evidence.
Measured, operator, imported, and modeled evidence remain distinguishable. Corrections create a
superseding record; approval and exclusion decisions are separate append-only evidence.

Exact WGS 84 locations can be retained only through an explicit choice. Generalized locations are
rounded before persistence, and redacted locations discard coordinates before persistence.
Versioned calibration sets preserve the selected observation/review digests, algorithm and
parameters, missing/outlier exclusions, incident-local recommendation, and transparent
before/after error comparison. No result overwrites or auto-promotes an organization default.

Approval fails closed until the exact `observation-envelope-v1-provisional` method passes the
configured security/privacy and qualified RF gate. Repository fixtures and tests remain synthetic.
See [ADR-0012](docs/adr/0012-field-observations-and-incident-local-calibration.md), the
[field observation and calibration guide](docs/operations/field-observations-and-calibration.md),
and the [Phase 2 data model](docs/data-model/phase-2.md).

## Explainable RF deconfliction decision support

Issue #39 evaluates one approved ICS-205 revision and an explicit selection of active
conventional-channel resources against stable, server-side rules for co-channel and
adjacent-channel area overlap, reversed repeater pairs, duplicate frequency pairs under different
names, missing technical values, selected active resources omitted from the plan, and missing
approved operating or coordination areas.

Every warning preserves its rule ID and version, severity, compared inputs, evidence, assumptions,
plain-language explanation, and decision-support disclaimer. CTCSS, DCS, NAC, and other squelch
differences remain visible evidence and never suppress a warning. Immutable input and result
snapshots and SHA-256 digests preserve the exact approved revision, selected resources, frozen
areas, rules, and output needed to reconstruct the result.

The initial `rf-deconfliction-v1-provisional` rule set is synthetic-evaluation decision support,
not frequency coordination, spectrum authorization, propagation analysis, or incident-command
authority. Approval fails closed until qualified COML, COMT, COMC, and frequency-coordination
practitioners accept the exact rules, severities, threshold, explanations, and positive, negative,
and boundary cases. See [ADR-0015](docs/adr/0015-versioned-rf-deconfliction-decision-support.md)
and the [RF deconfliction operations guide](docs/operations/rf-deconfliction.md).

## Accessibility

The Toolkit targets WCAG 2.2 Level AA across complete user processes. GitHub
Actions enforces JSX accessibility linting and axe-core checks on desktop and
320-CSS-pixel presentations, together with keyboard, skip-link, and document
reflow checks. Coordinate forms, structured result tables, and radio-site lists
provide non-pointer and nonvisual alternatives to map interactions.

Automated results are evidence, not a conformance claim. Release and deployment
candidates also require recorded keyboard, zoom/reflow, contrast, screen-reader,
and generated-content evaluation. See the
[accessibility standard](docs/governance/accessibility-standard.md) and
[accessibility review procedure](docs/operations/accessibility.md).

## TX-COMU brand system

The interface uses the approved TX-COMU digital colors and exact locally
vendored organization logo assets. It does not depend on GitHub, WordPress, a
content delivery network, or a remotely hosted font for its identity.

See the [brand asset provenance record](docs/governance/tx-comu-brand-assets.md)
for upstream paths, the exact source commit, file digests, usage boundaries, and
the required human approval gate.

## Important limitations

Coverage displays and conflict warnings produced by ICT Branch Toolkit are planning estimates only. They are not propagation studies, frequency coordination approvals, spectrum authorizations, or guarantees of radio coverage. Terrain, buildings, interference, equipment condition, antenna systems, subscriber performance, and other factors can materially affect actual operation.

Users remain responsible for complying with applicable laws, licenses, channel-use restrictions, coordination requirements, agency policies, and the current NIFOG. Reference to FEMA, CISA, NIFOG, ICS forms, or TAK does not imply endorsement of this project by those organizations or programs.

## Contributing

The project is currently establishing its requirements and architecture. Early participation is welcome through GitHub Issues, particularly from COML, COMT, COMC, ITSL, INCM, AUXCOMM, public-safety radio, GIS, and emergency-management practitioners.

Please do not submit real incident data, protected channel information, credentials, private keys, certificates, personal information, or other sensitive material to the public repository.

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and the
operations guides above for the current contributor, reporting, development,
and evaluation procedures.

## License

ICT Branch Toolkit is licensed under the [GNU Affero General Public License v3.0](LICENSE). Additional attribution, trademark, and third-party notice files will be added before the first public release.

## Origin and attribution

ICT Branch Toolkit was originally developed by the [Texas Communications Unit (TX-COMU)](https://tx-comu.org).

The ICT Branch Toolkit name identifies the open-source software project. The TX-COMU name and logo are not licensed for use in a way that implies sponsorship, certification, or endorsement of a third-party installation or modified version.
