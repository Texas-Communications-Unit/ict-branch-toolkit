# Issue 130 — Integrated Validation and Human Review Record

## Scope

This record covers the integration gate for Issue #125 after completion of #126, #127, #128, and #129. It does not replace the implementation-specific tests or documentation from those issues. It records the combined operator workflow, automated evidence expected before merge, and the human review that remains required before #125 can be accepted.

## Integrated operator workflow under review

1. Enter a supported address, intersection, coordinate string, or optional-provider identifier in the map location search.
2. Resolve the input to a provider-neutral WGS 84 result while preserving the operator's original entry.
3. Select a result and send the normalized coordinate into the existing map preview workflow.
4. Inspect incident-created sites and FCC/reference objects without conflating their identity or provenance.
5. Select an FCC/reference object by pointer or keyboard and keep the map marker, non-map result, and details panel synchronized.
6. Review tower/license/frequency details with US customary companion units while retaining source metric values.
7. Review exact integer-Hz NIFOG reference matches, including every applicable identifier and the effective source/release provenance.
8. Continue core coordinate/site planning when optional geocoding, what3words, FCC enrichment, or NIFOG enrichment is unavailable.

## Automated integration evidence

The Issue #130 Playwright regression uses deterministic synthetic fixtures only and verifies:

- local coordinate resolution remains available with external lookup disabled;
- successful search results populate the existing map coordinate workflow rather than creating a second parser or map path;
- keyboard FCC selection synchronizes marker, non-map result, and details state;
- selection has explicit text/ARIA semantics and is not color-only;
- incident-created site controls are not assigned FCC selection identity;
- FCC height presentation is converted through the existing shared unit enhancer (`328 ft (100 m)` for the synthetic 100 m case);
- FCC provenance remains visible in the details surface;
- multiple exact-frequency NIFOG identifiers can coexist in one reference result;
- NIFOG source/release information remains visible;
- the decision-support warning explicitly states that a match does not authorize transmission;
- Escape closes the selected FCC detail and restores focus to the originating control.

The upstream issue suites remain authoritative for the implementation-specific cases:

- #126: coordinate syntax, provider separation/fallback, privacy behavior, keyboard result selection;
- #127: pointer/keyboard map-object selection, synchronized highlight, focus restoration, non-color state;
- #128: conversion constants, rounding, null/unknown values, and screen-reader-friendly unit presentation;
- #129: canonical integer-Hz matching, one-to-many identifiers, release selection, inactive/draft exclusion, provenance, and authorization disclaimer language.

## Repository validation required on the exact candidate commit

Before merge, the exact candidate commit should pass all applicable repository checks, including:

### Frontend

- format check;
- lint/accessibility lint;
- TypeScript typecheck;
- component/unit tests;
- production build;
- Playwright browser tests, including the Issue #130 integrated regression.

### Backend

- formatter/linter;
- Django system checks;
- migration consistency checks;
- applicable backend test suite;
- schema/API checks for changed surfaces.

### Security and repository controls

- secret scan;
- CodeQL for applicable languages;
- dependency audit where dependency surfaces change;
- container build/security and SBOM checks where applicable;
- workflow policy checks required by the repository.

Automated checks are evidence for the engineering target; they are not a WCAG conformance claim and do not replace operational review.

## Accessibility review record

Automated coverage addresses keyboard operation, explicit selected state, focus restoration, status text, non-map FCC result access, and non-color semantics. The following items remain human review requirements on the exact release candidate:

- keyboard-only walkthrough of the full search-to-reference workflow;
- screen-reader walkthrough of search status, result selection, FCC selection, detail close/focus restoration, units, provenance, and NIFOG match announcements;
- 200% text resize review;
- 400% browser zoom/reflow review;
- 320 CSS-pixel responsive review;
- visual focus visibility and order review;
- confirmation that incident-created sites and FCC/reference objects are distinguishable without relying on color;
- confirmation that NIFOG reference-match state remains understandable without relying on color.

Record the reviewer, exact commit SHA, browser/assistive-technology combination, date, and findings before claiming acceptance under #61.

## Incident-communications human gate

A qualified COML, COMT, COMC, or equivalent incident-communications reviewer must evaluate the exact release candidate before #125 closes. Review should confirm:

- the end-to-end workflow is operationally understandable;
- FCC/reference provenance and limitations are clear;
- US customary companion units do not obscure the authoritative source values;
- NIFOG identifiers and RX/TX relationships are presented accurately;
- exact-frequency matches are not represented as frequency coordination, authority to transmit, licensing applicability, or proof of emission/service interoperability;
- degraded behavior is acceptable when optional providers or reference libraries are unavailable.

Record reviewer identity/role, exact commit SHA, review date, and any required follow-up in the #130 issue or final PR review.

## Provider and privacy gate

Core local coordinate planning must remain usable without an external provider. Any live external geocoder or what3words provider remains subject to #30 and requires separately approved configuration, terms, privacy, rate-limit, attribution, and operational-use decisions. No provider purchase, credential provisioning, or protected-location use is authorized by #130.

## Acceptance boundary

Issue #130 can provide automated integration evidence and document the human-review checklist, but #125 should not be closed until:

1. the exact candidate commit passes the applicable automated checks;
2. maintainer review accepts the combined workflow;
3. the qualified incident-communications review is recorded;
4. the human accessibility review items are recorded;
5. any live optional-provider configuration has the required policy/terms approval.

Do not infer deployment approval, interoperability authorization, licensing authority, or WCAG conformance solely from this document or automated test results.
