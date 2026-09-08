# Issue 125 — Map Search and Reference Enrichment Work Package

## Purpose

This document defines the implementation contract for Issue #125 and its child work items. It is intentionally provider-neutral, source-aware, accessibility-first, and compatible with the ICT Branch Toolkit's existing architecture and governance.

## Parent issue

- #125 — Feature: Add map search, object callouts, US units, and NIFOG frequency enrichment

## Delivery sequence

1. #126 — normalized map location search and coordinate resolution
2. #127 — accessible map object callouts and synchronized selection
3. #128 — US customary companion units for FCC/reference measurements
4. #129 — NIFOG interoperability frequency enrichment
5. #130 — integrated validation, accessibility, documentation, and final workflow review

#126 through #129 may proceed independently where their existing dependencies are satisfied. #130 is the integration gate.

## Existing architecture that must be reused

- #4: canonical coordinate parsing, radio sites, MapLibre workflow, WGS 84 storage
- #105: authoritative FCC ASR/ULS map/reference data
- #2: versioned channel libraries and NIFOG source/version provenance
- #30: map/geocoder licensing, attribution, privacy, rate-limit, caching, and provider policy
- #61: WCAG 2.2 Level AA engineering target and human-evaluation requirements
- #28: TX-COMU brand tokens and visual treatment
- #123: point elevation, which is complementary and should remain independently usable

Do not create duplicate source models, duplicate coordinate parsers, or frontend-only copies of authoritative FCC or NIFOG reference data.

## Capability contract

### 1. Unified location search

Provide one operator-facing search input with deterministic parsing before any external lookup.

Supported classes:

- decimal degrees
- DMS
- DDM
- other coordinate syntaxes already supported by the canonical parser
- common copied Google Maps latitude/longitude strings
- street addresses
- cross-street/intersection queries
- what3words when an approved, configured provider exists

All successful results normalize to WGS 84 latitude/longitude. Preserve the original entered representation for operator review where useful.

External geocoding must be behind a replaceable server-side provider interface. Provider unavailability must not block local coordinate parsing or core site planning.

Do not scrape or depend on Google Maps. Google-origin text is accepted only as coordinate syntax supplied by the operator.

what3words is optional. It must fail closed when provider configuration or terms are not approved.

### 2. Search result model

Normalize location lookup responses to a provider-neutral shape sufficient for the frontend to render a result list and map preview. Suggested fields:

- `latitude`
- `longitude`
- `display_name`
- `input_type`
- `provider`
- `provider_result_id` when permitted
- `confidence` or provider quality indicator when available
- `context` / locality text
- `original_query`
- `retrieved_at` for external results
- `warnings`

Do not persist external provider payloads merely because a search was performed. Persist only deliberately selected data needed by an approved workflow and only when source terms permit it.

### 3. Accessible map object selection

Mapped radio sites and FCC/reference objects must support selection through both pointer and non-pointer workflows.

Selecting an object must:

- identify the object in a details callout or companion panel;
- synchronize with the corresponding non-map result or reference record;
- expose the same substantive information through an accessible non-map path;
- preserve focus and provide a predictable close/escape interaction;
- distinguish incident-created sites from external reference objects;
- preserve source/provenance and stale/retrieval indicators.

Use an approved TX-COMU orange/accent treatment for selection where appropriate, but include non-color semantics such as text, iconography, outline/shape, or explicit selected state.

### 4. FCC/reference US customary companion units

Canonical/source values remain unchanged.

Presentation rules:

- height: feet first with meters retained in parentheses when appropriate;
- distance: miles first with metric source value retained in parentheses where appropriate;
- unknown/ambiguous source units are not converted;
- API responses must label units explicitly;
- conversion and rounding logic belongs in shared helpers, not duplicated component arithmetic.

Examples:

- `328 ft (100 m)`
- `6.2 mi (10 km)`

Conversions are derived presentation values, not rewritten FCC data.

### 5. NIFOG interoperability enrichment

Match reference/license frequencies to the approved, loaded NIFOG library using canonical integer hertz.

Requirements:

- exact frequency matching only unless a later issue explicitly defines another rule;
- preserve one-to-many matches;
- return every applicable NIFOG identifier for the exact matched frequency relationship;
- preserve NIFOG release/source/version provenance;
- gracefully handle no approved NIFOG library;
- do not hard-code NIFOG channels in frontend source;
- do not imply authorization, coordination approval, or licensing applicability from a frequency match.

Example acceptance case: when the approved loaded NIFOG version contains multiple identifiers on 159.4725 MHz, the enrichment result must return all applicable identifiers rather than choosing one.

### 6. Integration behavior

A typical end-to-end operator path should support:

1. Enter an address, intersection, coordinate string, or approved optional provider identifier.
2. Resolve or parse to one or more WGS 84 candidate locations.
3. Select a result and preview/center it on the map.
4. Inspect nearby or selected incident/FCC objects using pointer or keyboard workflows.
5. View tower/license/frequency details with operator-friendly companion units.
6. See NIFOG interoperability identifiers where exact approved-library matches exist.
7. Continue site planning even if optional geocoding, what3words, FCC enrichment, or NIFOG enrichment is unavailable.

## Security and privacy constraints

- No credentials, API keys, protected coordinates, or real incident data in source, fixtures, screenshots, logs, or public issue text.
- Public geocoders must not receive protected incident locations without an approved operational/privacy determination.
- Provider errors must be sanitized and bounded.
- External requests require configured allowlisting, timeouts, response-size limits, and rate controls consistent with existing provider patterns.
- Server-side authorization remains authoritative.

## Accessibility definition of done

The complete workflow must comply with the repository's WCAG 2.2 AA engineering target and #61 requirements, including:

- keyboard-only search and result selection;
- keyboard-accessible object details without requiring map clicking;
- visible focus and logical focus restoration;
- non-color-only selected and NIFOG-match states;
- accessible names for controls and map alternatives;
- status/error announcements;
- 200% text resize and 400% zoom/reflow review;
- 320 CSS-pixel responsive behavior;
- automated accessibility checks plus recorded human-review items.

Automated checks are not a WCAG conformance claim.

## Verification expectations

### Backend

- formatter/linter
- Django checks
- migration checks
- complete applicable test suite
- API/schema tests
- provider failure and authorization tests
- exact integer-Hz NIFOG matching tests
- conversion-helper tests where backend-derived values are exposed

### Frontend

- formatting
- accessibility lint
- type checking
- component tests
- build
- browser tests for search, selection synchronization, failure states, keyboard operation, and non-color semantics

### Repository/security

Run all applicable CI, dependency, secret, workflow, container, security, and SBOM checks required by the repository.

## Human gates

Before #125 is accepted:

- maintainer review of the combined workflow;
- qualified incident-communications review of NIFOG interpretation and operator language;
- accessibility review items recorded per #61;
- provider/terms approval for any live external geocoding or what3words implementation.

## Non-goals / prohibited assumptions

- No paid provider is required.
- No automatic provider purchase or account creation.
- No Google Maps dependency or scraping.
- No silently persisted external search results.
- No rewriting imported FCC records with converted values.
- No hard-coded NIFOG duplication.
- No frequency-match result represented as authority to transmit.
- No merge, deployment, DNS change, or secret provisioning is authorized by this work package.
