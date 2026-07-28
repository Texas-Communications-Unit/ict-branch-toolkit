# ADR-0009: Source-aware elevation and reproducible HAAT

- Status: Accepted for P2.2 prototype implementation
- Date: 2026-07-27
- Decision owners: Maintainers; qualified GIS and RF review remains required

## Context

Phase 2 needs site elevation and height above average terrain (HAAT) without coupling the
application to one commercial service, one terrain product, or one regulatory method. Elevation
values are meaningless without horizontal and vertical references, source/version provenance,
coverage and resolution, license terms, and the exact sampling and transformation path.

Network access cannot be a prerequisite for core planning or automated tests. A transient provider
response also cannot be allowed to change a previously approved result.

## Decision

Use a server-selected, replaceable `ElevationProvider` interface. Browser requests never supply a
provider class or remote URL. A configured source is called only when its complete source
descriptor—provider, product, reference systems, resolution, version, license/terms, permitted
use, coverage, content digest, and offline/network mode—exactly matches an entry in
`ICT_APPROVED_ELEVATION_SOURCES`.

The safe default is `DisabledElevationProvider`. The repository includes an offline
`SyntheticElevationProvider` solely for deterministic tests, training, and demonstrations. Its
records and warnings identify the data as synthetic and unsuitable for operational decisions.
No third-party terrain is bundled or enabled.

Each exact radial query creates or reuses an immutable `ElevationSnapshot` containing:

- provider and dataset/product;
- horizontal, source vertical, and target vertical reference systems;
- nominal resolution, source version or retrieval time, permitted use, license/terms reference,
  coverage, and source content digest when supplied;
- complete query and sample snapshots with SHA-256 digests;
- transformation metadata, warnings, retrieval time, expiration time, and acquisition state.

The cache is incident- and site-scoped. Only unexpired entries with the exact canonical query
digest may be reused. A retry or explicit refresh creates a new snapshot. Expired entries remain
retained and report `stale`; they are never rewritten.

`HAATCalculation` is a retained result record that references the exact site, immutable approved
RF input snapshot and profile version, elevation snapshot, algorithm snapshot, exclusions,
warnings, and result digest. The implemented method is
`haat-radial-average-v1-provisional`:

1. Generate WGS 84 sample points using a documented mean-radius sphere.
2. Acquire the site point and configured radial points.
3. Use provider-supplied transformed elevations only where sample state is `complete`.
4. Add the approved RF input snapshot's explicit antenna-center AGL to site elevation.
5. Subtract the arithmetic mean of usable radial terrain elevations.
6. Round each reported result to the recorded increment.

The record includes radial count, all azimuths, sampling interval, inner and outer limits,
endpoint handling, coordinate transformation, exclusions, partial-result rule, and rounding.
Missing site elevation or no usable terrain produces `unavailable`. Some missing radial samples
produce `partial`; partial and unavailable results cannot be approved. A retry creates a new
calculation linked through `supersedes`. A complete draft may be approved and locked.

The method is described as a general planning radial-average terrain method. The application does
not claim it controls FCC, NTIA, coordination, licensing, or any particular land-mobile-radio
service.

## Consequences

- Results are reproducible from immutable input, source, sample, algorithm, and digest records.
- Operators see complete, partial, missing, out-of-coverage, and stale source states.
- External source enablement is an explicit server-side approval decision.
- Network/provider failures do not rewrite existing evidence; operators can retry into a new
  record.
- Cached sample coordinates and elevations inherit incident access controls and backup/retention
  requirements.
- The prototype does not ship a real elevation provider. Qualified maintainers must approve and
  implement one before actual terrain is enabled.

## Alternatives considered

- **Call a public elevation URL directly from the browser:** rejected because it exposes incident
  coordinates, bypasses server authorization and source approval, and is not reproducible.
- **Store only the resulting HAAT number:** rejected because it loses source, datum, sampling,
  exclusions, and algorithm evidence.
- **Silently use an FCC broadcast HAAT convention for every workflow:** rejected because the
  applicable method depends on service, purpose, and governing authority.
- **Replace stale cache entries in place:** rejected because it would change the evidence behind
  prior results.
