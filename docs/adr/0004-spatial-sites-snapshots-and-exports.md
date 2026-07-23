# ADR-0004: Spatial sites, approval snapshots, and portable exports

Status: Accepted for P1.3

## Context

P1.3 requires a PostGIS-backed radio-site workflow that remains testable without a paid map, API key, or local PostGIS installation. Approved plans must not change when a canonical incident site is later corrected. Coordinate entry must accept decimal degrees, DDM, DMS, and USNG/MGRS while preserving the operator's original representation.

## Decision

Store each radio site as an incident-scoped WGS 84 point (SRID 4326), with six-decimal latitude and longitude fields for deterministic interchange. `PortablePointField` is a spatially indexed GeoDjango `PointField` when PostGIS is enabled and a GeoJSON-compatible field in credential-free SQLite tests. Bounding-box API tests exercise the PostGIS spatial query in CI.

Manual operational, fringe/uncertain, and coordination rings store only their canonical radius in integer meters. MapLibre derives display polygons client-side without a network base map.

Assignments and sites use an explicit many-to-many link. Approval freezes the site, coordinate provenance, source identity, and ordered rings into each link. Official spatial exports read only those snapshots. Copying an approved plan carries the canonical site links into a new draft but deliberately clears the old snapshots.

Approved output formats are deterministic GeoJSON, CSV, KML, and an offline SVG map. SVG was selected as the first map output because it is open, scalable, printable, and does not require a screenshot service or proprietary basemap.

The address lookup is a replaceable provider interface. Its default implementation returns no results. Enabling a network provider requires separate configuration and review.

## Consequences

- Later site edits cannot silently alter an approved export.
- PostGIS provides the production spatial index and query behavior; SQLite remains a deterministic local test fallback.
- The first SVG map shows sites and manual rings on a neutral field, not streets, terrain, or predicted coverage.
- Rings are operator-entered planning annotations, not calculated propagation contours.
- External FCCInfo, Google Earth, geocoding, or paid-map dependencies are not introduced by this decision.
