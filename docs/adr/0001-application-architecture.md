# ADR-0001: P1.0 application architecture

- Status: Accepted for prototype
- Date: 2026-07-22
- Decision owners: Project maintainers

## Context

The toolkit needs mature authorization and revision patterns, spatial storage and queries, a portable browser map, reproducible local development, and a path to later offline and integration work. The public prototype must not require a paid map provider or production key.

## Decision

Use Python 3.12 with Django 5.2 LTS, GeoDjango, Django REST Framework, PostgreSQL 17 with PostGIS 3.5, React 19, TypeScript, Vite, and MapLibre GL JS. Use Docker Compose for the local integration environment, pytest for backend tests, Vitest/Testing Library for frontend tests, Playwright for browser tests, and GitHub Actions for CI.

Map style and API base URLs are configuration. The default map uses an inline, network-free MapLibre style so tests and the shell do not depend on credentials. Use token authentication only as a contained local prototype mechanism; production authentication and token lifecycle require a later ADR.

## Consequences

The stack supplies mature migrations, administration, validation, spatial primitives, typed UI development, and provider-neutral mapping. Contributors need Docker for the full PostGIS path. SQLite is permitted only for fast non-spatial unit/API tests. The initial UI and data model are intentionally thin and must not be mistaken for production readiness.

## Alternatives considered

- A single Django-rendered UI would reduce moving parts but constrain the planned interactive map/editor experience.
- A Node-only backend would align languages but require assembling more authorization, administration, and audit infrastructure.
- A proprietary hosted mapping API could speed initial cartography but would violate portability and credential-free test requirements.

