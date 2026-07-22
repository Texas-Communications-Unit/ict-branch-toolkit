# P1.0 Dependency Baseline

Selected on 2026-07-22 from the official PyPI and npm package registries, then installed and verified together. Exact direct versions are pinned in `backend/pyproject.toml` and `frontend/package.json`; the frontend transitive graph is locked in `frontend/pnpm-lock.yaml`.

## Runtime baseline

| Component | Selected version | Rationale |
| --- | --- | --- |
| Python | 3.12 | Supported, conservative runtime for Django 5.2 LTS |
| Django | 5.2.16 | Current 5.2 long-term-support line rather than the newer non-LTS major |
| Django REST Framework | 3.17.1 | Current stable API framework compatible with Django 5.2 |
| PostgreSQL/PostGIS image | 17 / 3.5 | Stable spatial database baseline with an official PostGIS project image |
| React / React DOM | 19.2.8 | Current stable UI runtime |
| TypeScript | 6.0.3 | Current stable version compatible with the selected type-aware tooling |
| Vite | 8.1.5 | Current stable build and development server |
| MapLibre GL JS | 5.24.0 | Mature stable release selected instead of the same-day 6.0 major |
| pnpm | 11.9.0 | Pinned package manager for reproducible installs |

## Verification policy

Renovate or Dependabot may propose upgrades later, but upgrades must remain isolated, pass the full check suite, and preserve the no-paid-provider and credential-free test boundaries. CI audits Python and JavaScript dependencies and reviews pull-request dependency changes. Official sources: [PyPI](https://pypi.org/), [npm](https://www.npmjs.com/), [Django](https://docs.djangoproject.com/en/5.2/), [PostGIS](https://postgis.net/docs/), [MapLibre GL JS](https://maplibre.org/maplibre-gl-js/docs/), and [Docker Compose](https://docs.docker.com/compose/).
