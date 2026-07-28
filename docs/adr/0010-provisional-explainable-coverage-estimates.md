# ADR-0010: Provisional explainable coverage-estimate engine

- Status: Proposed; implemented for synthetic evaluation only
- Date: 2026-07-28
- Issue: #17

## Context

Phase 2 needs reproducible band- and environment-aware planning estimates before the later
talk-out/talk-in, field-calibration, and terrain-analysis milestones. The Toolkit already retains
approved RF input snapshots, source-aware elevation evidence, reproducible HAAT results, and
operator-entered Phase 1 rings. It must not silently replace any of those records or present a
calculated distance as measured coverage, regulatory analysis, coordination approval, or a
guarantee.

Selecting an operational propagation method, band domain, clutter/environment model, receiver
profile, threshold, and uncertainty treatment requires qualified RF engineering and incident
communications review. No such method has yet passed that human gate. The first implementation
therefore needs to exercise the replaceable-engine contract and evidence workflow while remaining
clearly provisional.

## Decision

Introduce a replaceable server-side `CoverageEstimateEngine` interface and one deterministic
synthetic-evaluation implementation:

`provisional_fspl_horizon` / `fspl-horizon-v1-provisional`.

The implementation:

1. accepts only an approved, complete `HAATCalculation`;
2. follows that record to its immutable approved `RFAnalysisInputSnapshot`;
3. requires explicit transmit frequency, effective radiated power, receiver sensitivity, and HAAT;
4. groups only explicitly configured frequency ranges;
5. converts ERP to EIRP using the recorded provisional `+2.15 dB` convention;
6. calculates a free-space link-budget distance after applying selected environment and fade
   margins;
7. calculates a provisional radio-horizon cap from nonnegative HAAT and the configured receiver
   height;
8. reports the minimum of link-budget distance, horizon, and configured maximum;
9. calculates conservative and optimistic sensitivity bounds by varying the configured margin;
10. rounds every distance using the versioned preset; and
11. produces deterministic WGS 84 circle geometry plus canonical input, model, and result digests.

Every result stores the engine and preset versions, formulas, exact compared inputs, intermediate
values, limiting factors, assumptions, exclusions, warnings, plain-language explanation, source
digests, and output geometry. Unsupported inputs create an explicit retained `unsupported` result
without fabricated geometry.

The default band groups, environments, margins, receiver height, distance limits, rounding, and
uncertainty values are testable provisional constants. Installations may supply versioned preset
overrides through `ICT_COVERAGE_PRESETS`; changing a preset version is required when any value that
can affect a result changes.

Draft calculation is permitted for synthetic review, but result approval fails closed unless
`ICT_APPROVED_COVERAGE_CONFIGURATIONS` contains the exact engine ID/version and preset
name/version accepted through the qualified human gate.

Manual Phase 1 rings remain a separate data source and map layer. Calculated nominal geometry uses
a dashed layer and an accessible table. Calculated results never overwrite manual rings.

## Initial provisional domains

The engine recognizes these inclusive integer-Hz groups:

| Group | Lower bound | Upper bound |
| --- | ---: | ---: |
| `vhf_low` | 30,000,000 | 88,000,000 |
| `vhf_high` | 136,000,000 | 174,000,000 |
| `uhf` | 380,000,000 | 520,000,000 |
| `700_mhz` | 698,000,000 | 806,000,000 |
| `800_mhz` | 806,000,001 | 869,000,000 |
| `900_mhz` | 896,000,000 | 941,000,000 |

The ranges are application configuration boundaries, not regulatory band definitions or evidence
of model validity. Gaps and out-of-range values are explicitly unsupported.

The implemented environment margins are open `6 dB`, rural `10 dB`, suburban `16 dB`, urban
`22 dB`, and dense urban `28 dB`. The balanced preset adds `12 dB` fade margin and a `±6 dB`
sensitivity range; the conservative preset adds `18 dB` fade margin and the same sensitivity
range. These values are placeholders for qualified review, not operational defaults.

## Consequences

- Results can be reproduced from immutable RF, HAAT, model, preset, and digest evidence.
- Operators see why a distance changed and which factor limited it.
- Unsupported values remain visible without extrapolation or false precision.
- A later approved engine can replace this implementation without changing the API aggregate.
- P2.4 can introduce separate talk-out and talk-in paths rather than stretching this single-path
  prototype beyond its stated scope.
- P2.5 can create approved local preset versions without rewriting prior estimates.
- Map users can compare calculated geometry with manual rings while non-map users receive the same
  distances, assumptions, warnings, and evidence in a semantic table.

The first implementation is not operationally approved. Its results must always say:

> Provisional planning estimate only—not a propagation study, frequency-coordination decision,
> spectrum authorization, or coverage guarantee.

## Human gate

Qualified RF engineering and incident communications practitioners must approve or replace:

- the calculation method and formulas;
- supported band domains and boundary behavior;
- environment categories and margins;
- ERP/EIRP treatment;
- fade margin, uncertainty, receiver height, maximum distance, and rounding;
- required inputs and unsupported conditions;
- conservative/nominal/optimistic wording;
- geometry and map presentation; and
- positive, negative, boundary, and unit-conversion test tables.

Approval of this ADR or a pull request is not approval for operational use. A decision that accepts
an engine for operational decision support must identify the exact engine version and preset
versions.

## Alternatives considered

- **Implement an empirical propagation model immediately:** rejected until qualified reviewers
  select the method, valid domains, data inputs, and limitations.
- **Return only one radius:** rejected because it conceals sensitivity to unapproved assumptions
  and creates false precision.
- **Infer missing RF values:** rejected because unknown is not zero and no operational defaults
  are approved.
- **Modify Phase 1 manual rings:** rejected because operator-entered and calculated evidence have
  different meanings and provenance.
- **Use browser-only calculations:** rejected because server authorization, immutable evidence,
  audit events, and deterministic exports would be bypassed.
