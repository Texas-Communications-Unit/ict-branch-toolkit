# Coverage-estimate evaluation and review

This guide covers the synthetic-evaluation workflow introduced for issue #17. It does not approve
the provisional method for operational use.

## Boundary

Every result is a planning estimate, not a propagation study, frequency-coordination decision,
spectrum authorization, or coverage guarantee. Use only synthetic or explicitly approved data.
Do not use the implemented provisional constants as agency defaults until the human gate in
[ADR-0010](../adr/0010-provisional-explainable-coverage-estimates.md) is complete.

The calculation does not:

- represent measured coverage;
- include terrain obstruction or diffraction analysis;
- distinguish talk-out and talk-in;
- determine probable two-way operation;
- establish interference protection;
- validate a frequency assignment or license; or
- replace operator-entered manual rings.

Those boundaries belong to later reviewed milestones.

## Required evidence

Creating an estimate requires:

1. an incident-scoped RF profile version with explicit transmit frequency, ERP, receiver
   sensitivity, and antenna AGL;
2. approval and locking of that profile version;
3. an immutable named RF analysis input snapshot;
4. a complete HAAT calculation tied to the same snapshot and radio site; and
5. approval and locking of the HAAT result.

The server follows the HAAT record to the exact RF input snapshot and rejects draft, partial, or
unavailable HAAT evidence. It does not accept caller-selected site coordinates or unversioned RF
values in the estimate request.

## Evaluation workflow

1. Select the incident.
2. Open **Band and environment estimates**.
3. Review the displayed engine version, supported band groups, environment margins, and presets.
4. Select one complete approved HAAT calculation.
5. Select the operating environment and a versioned preset.
6. Create the estimate.
7. Review conservative, nominal, and optimistic distances in the semantic table.
8. Expand **Explanation and digests** and review:
   - the plain-language explanation;
   - warnings and exclusions;
   - engine and preset versions;
   - RF input digest;
   - HAAT result digest; and
   - estimate result digest.
9. Compare the dashed calculated nominal layer with the separate solid manual-ring layer. A map is
   optional; the table contains the accessible equivalent.
10. Approve and lock a complete result only when it accurately preserves the intended synthetic
    evaluation evidence.

An `unsupported` result is retained to show why no geometry was produced. It cannot be approved.

## Configuration

The default replaceable engine is:

```text
ICT_COVERAGE_ENGINE=apps.rf_analysis.coverage.ProvisionalFsplHorizonEngine
```

Local preset overrides use a JSON object:

```text
ICT_COVERAGE_PRESETS={}
```

Each preset contains:

- `version`;
- `fade_margin_db`;
- `uncertainty_db`;
- `receiver_height_m`;
- `maximum_distance_m`; and
- `distance_rounding_m`.

Changing any value that can affect a result requires a new, reviewable preset version. Do not
silently reuse a prior version name. Environment margins and band groups are engine-versioned; a
change requires a new engine version.

Approval fails closed. After the qualified human gate, an administrator records only the exact
accepted engine and preset identities:

```text
ICT_APPROVED_COVERAGE_CONFIGURATIONS=[{"engine":"provisional_fspl_horizon","engine_version":"fspl-horizon-v1-provisional","preset":"balanced","preset_version":"balanced-v1-provisional"}]
```

An empty list permits synthetic draft calculations and review but prevents approval. Changing any
engine or preset version removes the match and requires a new human decision. Recording an
allowlist entry does not authorize deployment, operational data, or any external service.

Invalid negative or unbounded preset values fail the request. An unknown preset creates an
explicit unsupported result rather than selecting an implicit default.

## Integrity and audit review

A result preserves:

- incident and radio-site identity;
- WGS 84 center coordinates at calculation time;
- RF snapshot identity, profile-version identity, approval time, and digest;
- HAAT identity, method version, approval time, value, and result digest;
- selected frequency, ERP, receiver sensitivity, environment, and preset;
- engine, engine version, formulas, constants, intermediate values, and limiting factors;
- conservative, nominal, and optimistic distances in integer meters;
- deterministic WGS 84 polygon geometry;
- warnings, exclusions, explanation, and disclaimer; and
- canonical input, model, and result digests.

Material create and approve actions enter the append-only audit chain. General audit details record
field names and source/result digests, not RF values.

To verify deterministic behavior, repeat the same request against the same approved source
records and configuration. The input and result digests must match. A changed engine, preset,
source digest, selected environment, site coordinate, or input must produce changed evidence.

## Practitioner review table

Record the exact code commit, engine version, and preset versions reviewed.

| Review area | Questions | Decision/evidence |
| --- | --- | --- |
| Purpose | Is a bounded single-path estimate useful before talk-out/talk-in analysis? | |
| Bands | Are the included ranges correct, and how should gaps/boundaries be handled? | |
| Link budget | Is the ERP-to-EIRP and receiver-threshold treatment appropriate? | |
| Environment | Are the categories meaningful and are margins defensible? | |
| Horizon | Is the provisional horizon formula appropriate, and in which conditions? | |
| Uncertainty | Are the sensitivity bounds and language understandable and conservative? | |
| Limits | Are maximum distance, receiver height, and rounding appropriate? | |
| Unsupported | Are missing/out-of-domain conditions rejected rather than extrapolated? | |
| Presentation | Are map layers, tables, warnings, and explanations operationally clear? | |
| Tests | Do positive, negative, boundary, and unit-conversion cases cover review concerns? | |

Create follow-up issues for every rejected assumption or required change. Do not mark issue #17
complete until the selected method, supported domains, test table, and published limitations pass
the qualified human gate.
