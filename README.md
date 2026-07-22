# ICT Branch Toolkit

ICT Branch Toolkit is an open-source web application for incident communications planning, radio-site mapping, coverage visualization, and frequency deconfliction. It is intended to support Communications Unit and Information and Communications Technology (ICT) Branch personnel during incidents, planned events, exercises, and pre-incident planning.

> **Project status:** P1.0 non-production prototype scaffold. No production-ready release is available yet, and the application must use synthetic data only.

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

- ERP, antenna height, AGL, HAAT, and subscriber profiles
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

## P1.0 vertical slice

The current slice provides token-based local authentication, administrator-only mutation, incident and operational-period creation, an authenticated incident list, an offline-safe MapLibre shell, PostGIS health verification, and synthetic automated tests. It does not yet implement channel libraries, ICS-205 revision control, site data, deconfliction, official exports, or production authentication hardening.

## Important limitations

Coverage displays and conflict warnings produced by ICT Branch Toolkit are planning estimates only. They are not propagation studies, frequency coordination approvals, spectrum authorizations, or guarantees of radio coverage. Terrain, buildings, interference, equipment condition, antenna systems, subscriber performance, and other factors can materially affect actual operation.

Users remain responsible for complying with applicable laws, licenses, channel-use restrictions, coordination requirements, agency policies, and the current NIFOG. Reference to FEMA, CISA, NIFOG, ICS forms, or TAK does not imply endorsement of this project by those organizations or programs.

## Contributing

The project is currently establishing its requirements and architecture. Early participation is welcome through GitHub Issues, particularly from COML, COMT, COMC, ITSL, INCM, AUXCOMM, public-safety radio, GIS, and emergency-management practitioners.

Please do not submit real incident data, protected channel information, credentials, private keys, certificates, personal information, or other sensitive material to the public repository.

Contributor guidance, security reporting instructions, development setup, and coding standards will be added with the initial application scaffold.

## License

ICT Branch Toolkit is licensed under the [GNU Affero General Public License v3.0](LICENSE). Additional attribution, trademark, and third-party notice files will be added before the first public release.

## Origin and attribution

ICT Branch Toolkit was originally developed by the [Texas Communications Unit (TX-COMU)](https://tx-comu.org).

The ICT Branch Toolkit name identifies the open-source software project. The TX-COMU name and logo are not licensed for use in a way that implies sponsorship, certification, or endorsement of a third-party installation or modified version.
