# ADR-0017: Optional source-aware terrain profile analysis

## Status

Accepted for non-production synthetic evaluation. Qualified GIS/RF,
security/privacy, operations, accessibility, licensing, and maintainer approval
of every real dataset and adapter remains pending.

## Context

The Phase 2 coverage estimate is deliberately coarse. It uses versioned RF and
HAAT evidence but does not evaluate terrain along a particular direction.
Phase 3 needs an optional terrain comparison that can explain where a sampled
path is obstructed without silently presenting that result as a more
authoritative replacement.

Terrain datasets differ in resolution, horizontal and vertical reference,
coverage, licensing, retrieval method, and update lifecycle. External services
can also receive sensitive incident coordinates. A browser-selected URL,
mutable result, undocumented model, or mandatory proprietary dependency would
break the Toolkit's provenance, security, offline, and reproducibility
boundaries.

## Decision

Use two replaceable server-side interfaces:

- `TerrainProfileProvider` returns a source descriptor, declared
  configuration, retrieval time, transformed samples, acquisition state,
  warnings, and transformation evidence.
- `TerrainAnalysisEngine` declares its method, version, capabilities,
  parameters, tested resource limits, and unsupported conditions, then consumes
  a retained provider profile.

The default `DisabledTerrainProfileProvider` performs no network or local
dataset access. Capability discovery remains available and reports the
provider as unavailable. A configured provider is called only when the exact
provider, provider version, dataset product/version, content digest, engine,
and engine version match one object in
`ICT_APPROVED_TERRAIN_CONFIGURATIONS`. The browser cannot select a provider,
URL, credential, dataset, or allowlist entry.

The repository includes `SyntheticTerrainProfileProvider` only for
deterministic tests and explicitly approved synthetic evaluation. Its flat,
ridge, valley, missing, boundary, out-of-coverage, datum-offset, and failure
modes are invented fixtures and are never actual terrain.

The initial `sampled-line-of-sight-v1-provisional` engine:

1. accepts one complete, approved Phase 2 coverage estimate whose HAAT evidence
   retains antenna AMSL;
2. generates bounded EPSG:4326 path positions from the retained site
   coordinate, explicit azimuth, maximum distance, and sample interval using
   the versioned spherical-destination method and declared mean-Earth radius;
3. rejects sampling finer than the source's declared resolution;
4. evaluates cumulative sampled line of sight using the declared receiver
   height, optional clearance, and a documented provisional effective-Earth
   radius factor of `1.333333333`;
5. does not interpolate missing or out-of-coverage samples;
6. reports the first obstruction or gap, continuous clear distance, profile
   states, edge effects, warnings, and exclusions; and
7. compares that result with the retained Phase 2 nominal distance. A
   difference is provisionally material at the larger of 10 percent or 1,000
   meters and is explicitly referred for qualified review.

The method does not implement diffraction, clutter, vegetation, structures,
reflections, multipath, or a frequency-dependent propagation model. It is
sampled screening only.

`TerrainAnalysis` is an incident-scoped retained staged-job record. Queueing
captures immutable source, Phase 2, HAAT, application, method, parameter, and
digest evidence. Running creates a separate result snapshot and digest.
Queued work can be cancelled before explicit synchronous execution. A failed
or cancelled record remains retained; retry creates a new record linked
through `supersedes`. Changed source or Phase 2 evidence makes an earlier
result stale instead of recalculating it.

Only a current `complete` result can be approved. Partial, unsupported, failed,
cancelled, and stale evidence remains visible but cannot be approved. Approval
is review of the exact retained evidence; it is not dataset, algorithm,
coverage, coordination, regulatory, or operational approval.

The initial resource guards are 200,000 meters and 1,001 samples. They are
defensive bounds, not a capacity or accuracy rating. A real local dataset or
external adapter requires a separate human gate covering license and
redistribution terms, attribution, datum/transformation, resolution, coverage,
accuracy language, privacy, authentication, network and timeout behavior,
response limits, monitoring, compute limits, and positive/negative/boundary
tests.

## Consequences

Terrain comparison remains optional and core planning remains usable when no
provider is available. Historical decisions retain the exact source and method
evidence needed for later review. Operators see Phase 2 and terrain results
side by side, including a structured profile table that does not require map
or color interpretation.

The first method is intentionally limited and can stop at the first gap. Its
deterministic synthetic performance does not establish accuracy against real
terrain or safe concurrent capacity. More sophisticated diffraction or local
GIS engines can implement the same interfaces, but each new dataset, engine,
or behavior-changing version requires a new exact approval and updated ADR,
tests, limits, documentation, and migration/API evidence as applicable.
