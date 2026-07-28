# ADR-0011: Separate directional paths and probable two-way overlap

- Status: Proposed; implemented for synthetic evaluation only
- Date: 2026-07-28
- Issue: #18

## Context

A single infrastructure-centered radius conceals the usual imbalance between a fixed station and a
portable, mobile, fixed, cache, gateway, or locally configured subscriber. Infrastructure
transmitter power and antenna height may support talk-out farther than a subscriber transmitter
supports talk-in. Presenting one undifferentiated distance can therefore overstate probable
two-way operation.

P2.3 provides a replaceable, versioned provisional estimate engine and immutable evidence. P2.4
must reuse that engine without rewriting manual Phase 1 rings or prior P2.3 results.

## Decision

Create an immutable `DirectionalCoverageAnalysis` from:

- one complete, approved infrastructure HAAT calculation and its exact RF input snapshot;
- one distinct, approved subscriber RF input snapshot in the same incident;
- one explicit operating environment; and
- one versioned P2.3 preset.

Calculate the paths independently:

- **talk-out** uses infrastructure transmit frequency and ERP with subscriber receiver
  sensitivity;
- **talk-in** uses subscriber transmit frequency and ERP with infrastructure receiver
  sensitivity.

Both directions use the approved infrastructure HAAT and subscriber antenna AGL to bound the same
concentric planning horizon. The exact path inputs, model evidence, formulae, warnings,
exclusions, and geometry are retained separately.

The provisional two-way rule is
`concentric-minimum-v1-provisional`:

```text
probable_two_way_nominal_distance_m =
  min(talk_out_nominal_distance_m, talk_in_nominal_distance_m)
```

The rule runs only when both paths are supported and the infrastructure transmit/receive
frequencies match the subscriber receive/transmit frequencies respectively. Missing inputs,
frequency mismatches, unsupported bands, or unsupported model conditions remain visible and
produce no probable two-way geometry.

Portable, mobile, fixed, cache, gateway, and configurable profile categories identify the
reviewed assumption set; they are not measured equipment facts or hidden defaults.

Approval fails closed unless both:

1. the exact P2.3 engine and preset are in `ICT_APPROVED_COVERAGE_CONFIGURATIONS`; and
2. `concentric-minimum-v1-provisional` is in `ICT_APPROVED_DIRECTIONAL_RULES`.

## Consequences

- Talk-out, talk-in, and probable two-way results remain distinct and reproducible.
- The limiting path is explicit instead of hidden inside one radius.
- Manual rings, P2.3 single-path estimates, and P2.4 directional layers remain separate.
- Profile or source changes require new approved snapshots and create new analyses rather than
  changing history.
- This concentric minimum rule does not account for terrain, directional antennas, interference,
  receiver voting, simulcast behavior, field measurements, or non-radial coverage.

Every result remains planning decision support—not a propagation study, frequency-coordination
decision, spectrum authorization, or coverage guarantee.

## Human gate

Qualified RF and incident-communications practitioners must approve or replace:

- subscriber profile categories and required path inputs;
- cross-frequency matching rules;
- the concentric minimum rule and its version;
- talk-out, talk-in, probable two-way, limiting-path, and confidence language;
- supported and unsupported conditions; and
- reciprocal, asymmetric, mismatch/no-overlap, boundary, profile-change, stale-input, and
  deterministic test tables.

Approval must identify exact engine, preset, and directional-rule versions. It does not authorize
deployment, operational data, external services, or claims of measured coverage.

## Alternatives considered

- **Use the P2.3 radius as two-way coverage:** rejected because it hides path imbalance.
- **Average talk-out and talk-in:** rejected because the weaker path limits two-way operation.
- **Automatically select a subscriber profile:** rejected because a plausible default creates
  false precision.
- **Overwrite older or manual layers:** rejected because they have different meaning and
  provenance.
