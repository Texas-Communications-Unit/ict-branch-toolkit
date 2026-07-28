# Elevation providers and HAAT operations

## Safe default

Elevation retrieval is disabled by default:

```dotenv
ICT_ELEVATION_PROVIDER=apps.rf_analysis.elevation.DisabledElevationProvider
ICT_APPROVED_ELEVATION_SOURCES=[]
ICT_ELEVATION_CACHE_TTL_SECONDS=604800
```

With this configuration, the authenticated interface reports that elevation is unavailable.
Existing snapshots and calculations remain readable. No network request is attempted.

## Human approval before enabling a source

Maintainers and qualified GIS/RF practitioners must review all of the following before enabling a
real provider:

1. provider identity and implementation;
2. exact dataset/product and source version or retrieval-date behavior;
3. geographic coverage and nominal resolution;
4. horizontal and vertical reference systems;
5. datum/transformation method, grids, models, and error behavior;
6. permitted use, attribution, redistribution, caching, and retention terms;
7. privacy impact of sending incident coordinates to a provider;
8. availability, authentication, rate limits, retry limits, and timeout behavior; and
9. whether the provisional HAAT method is suitable for the intended service and decision.

The provider class is selected only in server configuration. Never accept a provider class,
hostname, URL, credential, or approval record from a browser request.

An enabled provider must expose an `ElevationSource` descriptor. The server calls it only when an
allowlist entry exactly matches every descriptor field: `provider`, `dataset_product`,
`horizontal_crs`, `vertical_crs`, `target_vertical_crs`, `resolution_m`, `source_version`,
`license_terms_url`, `permitted_use`, `coverage`, `source_content_sha256`, and `offline`.
Example structure:

```dotenv
ICT_ELEVATION_PROVIDER=approved.package.ApprovedElevationProvider
ICT_APPROVED_ELEVATION_SOURCES=[{"provider":"reviewed-provider-id","dataset_product":"Reviewed product name","horizontal_crs":"reviewed-horizontal-reference","vertical_crs":"reviewed-source-vertical-reference","target_vertical_crs":"reviewed-target-vertical-reference","resolution_m":"reviewed-resolution","source_version":"reviewed-version","license_terms_url":"https://reviewed.example.invalid/terms","permitted_use":"Exact reviewed permitted-use statement","coverage":{"reviewed":"coverage descriptor"},"source_content_sha256":"reviewed-lowercase-sha256","offline":false}]
```

This example is a structure, not an approved source. Do not place credentials in this JSON or
commit operational provider configuration.

## Offline synthetic fixture

The bundled synthetic provider is deterministic and requires no network:

```dotenv
ICT_ELEVATION_PROVIDER=apps.rf_analysis.elevation.SyntheticElevationProvider
ICT_SYNTHETIC_ELEVATION_MODE=flat
ICT_APPROVED_ELEVATION_SOURCES=[{"provider":"synthetic-offline","dataset_product":"ICT Toolkit deterministic terrain fixture (flat)","horizontal_crs":"EPSG:4326","vertical_crs":"SYNTHETIC:LOCAL","target_vertical_crs":"SYNTHETIC:LOCAL","resolution_m":"30.000","source_version":"synthetic-terrain-v1","license_terms_url":"https://github.com/Texas-Communications-Unit/ict-branch-toolkit/blob/main/docs/operations/elevation-and-haat.md#offline-synthetic-fixture","permitted_use":"Synthetic fixture data only; not terrain, not for operational decision support.","coverage":{"type":"synthetic","extent":"global"},"source_content_sha256":"708c6ea14b7522f3b892d34cac2892e7fa399499ccf1e871a1b69b18e5070f90","offline":true}]
```

Allowed fixture modes are `flat`, `slope`, `rugged`, `missing`, `boundary`,
`out_of_coverage`, and `datum`; `failure` exercises the retryable provider-error path. The fixture
must never be described or used as actual terrain.

For an operationally approved offline provider, preload its source material through that
provider's reviewed procedure, keep it on protected application storage, and retain its content
digest and version. The toolkit does not include a general upload endpoint for terrain files.

## Calculation and retry behavior

The operator selects:

- an incident radio site;
- an immutable approved RF input snapshot whose profile version has explicit antenna-center AGL;
- radial count and starting azimuth;
- inner and outer distance limits;
- sample interval; and
- result rounding increment.

The server records every generated azimuth and distance. If the exact query has an unexpired
snapshot, the cache is reused. Selecting **Bypass an unexpired cache entry** or using **Retry with
fresh elevation data** creates a new elevation snapshot. A retry also creates a new HAAT result
linked to the earlier attempt; it does not overwrite the earlier record.

Defensive validation permits 4 through 360 radials, distances through 100,000 meters, and no more
than 10,000 terrain samples in one request. These are request-safety limits, not approved RF or
method defaults.

Source states:

| State | Meaning | Operator action |
| --- | --- | --- |
| `complete` | Site and all requested terrain samples are present. | Review provenance and method; qualified approver may lock the result. |
| `partial` | Some requested samples are missing or outside coverage. | Review exclusions and retry or select an approved source with coverage. Partial results cannot be approved. |
| `missing` | The provider is disabled, unapproved, failed to supply values, or returned missing data. | Correct configuration/source availability, then retry. |
| `out_of_coverage` | The source reports that none of the requested points are covered. | Select a reviewed source with coverage; do not extrapolate silently. |
| `stale` | The cache retention interval expired. | Existing result remains reproducible; retrieve a new snapshot for new work. |

## Verification after configuration change

1. Open **Elevation and HAAT** and confirm the expected provider/product and approval status.
2. Confirm horizontal and vertical reference systems, resolution, version, and permitted use.
3. Run a synthetic or explicitly approved non-sensitive test site.
4. Verify sample and result SHA-256 values are present.
5. Confirm expected result and source state.
6. Use retry and verify that it creates a new result and elevation snapshot.
7. Review application audit events for create, retry, and approval actions.

Do not treat a successful request as validation of terrain accuracy, datum transformation,
regulatory applicability, frequency coordination, spectrum authorization, or predicted coverage.

## Rollback

Set `ICT_ELEVATION_PROVIDER` back to
`apps.rf_analysis.elevation.DisabledElevationProvider`, clear
`ICT_APPROVED_ELEVATION_SOURCES`, and restart the backend through the approved deployment
procedure. This prevents new retrievals without deleting prior snapshots or calculations.
