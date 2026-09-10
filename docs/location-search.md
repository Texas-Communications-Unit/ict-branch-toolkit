# Normalized map location search

Issue #126 adds one operator-facing location resolver for the radio-site planning map. Every successful result is normalized to WGS 84 (`EPSG:4326`) while the original operator-entered query remains present in the response for review.

## Resolution order

1. The server first attempts deterministic local parsing with the existing canonical coordinate parser from the sites application.
2. Supported local syntax includes decimal degrees, DDM, DMS, MGRS/USNG, and common copied Google Maps URLs containing an `@latitude,longitude` coordinate pair.
3. Google-style inputs are treated only as coordinate syntax. The application does not call, depend on, or scrape Google Maps.
4. If local parsing does not match, the resolver classifies a three-word address as what3words input; otherwise it treats the query as an address/intersection candidate for the configured geocoder.
5. External lookup is performed only when the request explicitly sets `external_lookup_allowed=true`.

## Privacy and operational data

External geocoding can disclose the submitted location text to the configured provider. Operators must leave external lookup disabled for protected incident locations or other sensitive operational information unless an appropriate operational/privacy determination authorizes the disclosure.

Local coordinate parsing never requires an external provider. If every external provider is disabled or unavailable, coordinate and manual map workflows remain available.

## General geocoder

The existing replaceable server-side geocoder interface remains authoritative. `ICT_GEOCODER_PROVIDER` selects the configured implementation. The default is `apps.sites.geocoders.DisabledGeocoder`.

The current public implementation is the U.S. Census MAF/TIGER single-line geocoder. Provider use must continue to follow the mapping/provider policy established under Issue #30, including applicable attribution, privacy, rate-limit, caching, and licensing requirements. Cross-street queries are returned as a textual result list; provider labels must include sufficient locality/context for an operator to distinguish ambiguous intersections before selection.

CI uses `apps.sites.geocoders.DeterministicTestGeocoder`, which returns synthetic-only fixtures and performs no network request.

## what3words adapter

what3words is optional and fail-closed. It is not a dependency for coordinates, addresses, or intersections.

Configuration is controlled by:

- `ICT_WHAT3WORDS_PROVIDER` — provider class path. The effective default is `apps.sites.what3words.DisabledWhat3WordsProvider`.
- `ICT_APPROVED_WHAT3WORDS_PROVIDERS` — JSON array of specifically approved provider class paths.

A configured what3words provider is used only when its class path is also present in the approved-provider list. Otherwise the application behaves as if what3words is disabled. API keys or commercial-provider credentials are not committed to the repository and no purchase is authorized by Issue #126.

CI uses `apps.sites.what3words.DeterministicTestWhat3WordsProvider` only when that synthetic provider is explicitly approved in the test settings.

## API behavior

`POST /api/locations/resolve/`

Request fields:

- `query`: original operator-entered location text.
- `external_lookup_allowed`: boolean; defaults to `false`.

Each successful result includes:

- `latitude` and `longitude` normalized to WGS 84.
- `crs: EPSG:4326`.
- decimal, DDM, DMS, and MGRS representations.
- the provider identity.
- the original query.

The response also states the resolution method, whether an external lookup was actually performed, whether the relevant provider is configured, and—when applicable—why an external lookup was blocked.

## Frontend behavior

The Map location search panel is mounted inside the existing Radio site planning workspace. Results are presented as ordinary keyboard-accessible buttons in a non-map textual list. Selecting a result writes the normalized decimal coordinate into the existing Coordinate field and invokes the existing Parse and preview action so site creation and map placement continue through the established MapShell workflow rather than a parallel implementation.
