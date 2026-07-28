# Directional coverage evaluation and review

This guide covers the synthetic-evaluation workflow introduced for Issue #18. It does not approve
the provisional directional rule for operational use.

## Boundary

Talk-out, talk-in, and probable two-way results are planning estimates. They are not propagation
studies, coordination decisions, spectrum authorizations, measured coverage, or guarantees.
Manual rings and prior single-path estimates remain separate.

## Required evidence

An analysis requires:

1. a complete, approved infrastructure HAAT calculation tied to an immutable RF snapshot;
2. a distinct, approved subscriber RF snapshot in the same incident;
3. explicit transmit and receive frequencies, ERP, receiver sensitivity, and subscriber antenna
   AGL;
4. an explicit environment and versioned P2.3 preset; and
5. matching infrastructure-transmit/subscriber-receive and
   subscriber-transmit/infrastructure-receive frequency pairs.

Archived, cross-incident, incomplete, mismatched, or unsupported inputs produce a rejection or an
explicit unsupported result rather than invented probable two-way geometry.

## Evaluation workflow

1. Select the incident.
2. Open **Talk-out, talk-in, and two-way analysis**.
3. Select approved infrastructure HAAT evidence.
4. Select a distinct approved subscriber snapshot and review its profile type and version.
5. Select the environment and exact preset.
6. Calculate the paths.
7. Review talk-out and talk-in separately.
8. Confirm that probable two-way distance is the smaller supported nominal path.
9. Review the limiting path, assumptions, warnings, exclusions, source digests, and result digest.
10. Compare the three directional map layers with separate manual and earlier calculated layers.

The semantic table is the accessible equivalent of the map.

## Configuration and approval

The directional rule gate is empty by default:

```text
ICT_APPROVED_DIRECTIONAL_RULES=[]
```

After qualified review, an administrator may record the exact accepted rule:

```text
ICT_APPROVED_DIRECTIONAL_RULES=["concentric-minimum-v1-provisional"]
```

The exact P2.3 engine and preset must also be approved through
`ICT_APPROVED_COVERAGE_CONFIGURATIONS`. Changing any engine, preset, or rule version requires new
evidence and a new human decision.

Configuration approval does not authorize deployment, external services, operational data, or
claims of measured performance.

## Review checklist

| Review area | Question | Decision/evidence |
| --- | --- | --- |
| Profiles | Are portable, mobile, fixed, cache, gateway, and configurable categories adequate? | |
| Inputs | Are ERP, receiver sensitivity, frequency pair, HAAT, and subscriber AGL sufficient? | |
| Frequencies | Should exact cross-frequency equality be required or explicitly toleranced? | |
| Path rule | Is separate directional calculation appropriate for the reviewed use? | |
| Two-way rule | Is the minimum supported nominal radius acceptable? | |
| Wording | Are probable two-way, limiting path, and unsupported labels clear? | |
| Presentation | Are the three layers and accessible table distinguishable? | |
| Tests | Do reciprocal, asymmetric, mismatch, boundary, profile-change, and stale cases suffice? | |

Create follow-up issues for every rejected assumption or required change. Do not consider Issue
#18 complete until the exact rule, profiles, wording, and tests pass the practitioner gate.
