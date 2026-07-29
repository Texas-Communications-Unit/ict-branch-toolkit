# ADR-0021: Practitioner-reviewed RF deconfliction

- Status: Accepted; operational allowlisting remains gated by integrated validation
- Date: 2026-07-29
- Issue: #39
- Supersedes: ADR-0015 for new analyses

## Context

The provisional RF deconfliction contract required practitioner decisions about operating intent,
frequency boundaries, missing evidence, subscriber compatibility, and retained review history.
Issue #39 records those decisions. Existing v1 analyses must remain interpretable, but new
analyses must not present a missing value, an unevaluated location, or a nonconventional system as
a conflict.

The feature remains decision support. It cannot coordinate frequencies, authorize spectrum,
determine interference, perform a propagation study, approve an ICS-205, or change an approved
plan automatically.

## Decision

New analyses use the stable identity `rf-deconfliction-v2-reviewed`. The server evaluates one
approved incident-scoped ICS-205 revision using these nonblocking findings:

- `RF-001`, critical: equal transmit frequencies with overlapping frozen approved operating or
  coordination areas;
- `RF-002`, warning: non-equal transmit frequencies separated by 12,500 Hz or less, inclusive,
  with overlapping frozen approved areas;
- `RF-003`, critical: inverse receive/transmit pairs on fixed-pair assignments, including
  relationships that may be intentional in interoperability plans such as VTAC repeaters;
- `RF-004`, warning: different channel names using the same non-null receive/transmit pair; and
- `RF-008`, critical: a directional assignment access code differs from the selected authoritative
  versioned source.

Touching area boundaries count as overlap. CTCSS, DCS, NAC, and equivalent access-code
differences never suppress `RF-001` or `RF-002`. `RF-002` is a conservative screening threshold,
not a band-plan or receiver-selectivity determination.

Each assignment records one operating classification:

1. fixed pair;
2. broadcast/transmit-only;
3. receive-only;
4. named system, with trunked, LTE/5G, SCADA, spread-spectrum, or other subtype;
5. dynamic/multi-channel pool; or
6. not yet determined, which is allowed only while the revision remains a draft.

One-way assignment entry requires an explicit user confirmation. Named systems and dynamic pools
may omit conventional frequencies without creating a missing-frequency warning. Candidate
resources may be retained for what-if planning and are not treated as plan omissions.

`RF-007` is retained as the not-evaluated status “Area overlap not evaluated.” It is not a
conflict or caution. Fixed-frequency rules similarly return explicit not-applicable statuses for
nonconventional classifications, and subscriber compatibility returns a not-evaluated status
when an authoritative expected value is unavailable. The engine never invents a location,
frequency, access code, or equivalence between unlike access-code formats.

`RF-008` compares receive values only with expected receive values and transmit values only with
expected transmit values. Transmit-only and receive-only assignments evaluate only their
applicable operating direction. Its source hierarchy is:

1. the selected versioned channel definition; then
2. an explicitly selected approved subscriber programming profile.

The selected source and all available comparison-source provenance are frozen in the input
snapshot. A mismatch warns that subscriber devices may not operate as intended and may require
special programming or other accommodations. It does not change the plan.

Every result retains canonical input and result snapshots and SHA-256 digests. Every finding has
a deterministic key. Authorized users may append, but never edit or delete, a finding disposition
of reviewed/no change, plan change required, special accommodation required, or source review
required. The audit chain records creation, approval, and each disposition without copying
sensitive frequency, access-code, coordinate, or explanation content.

Every result displays this exact disclaimer:

> Decision support only. Results do not constitute frequency coordination, spectrum
> authorization, an interference determination, a propagation study, or operational approval.
> Qualified practitioners must review the results before operational use.

Approval fails closed unless the exact version is server-allowlisted and both retained digests
reproduce. The default allowlist remains empty until the complete local, CI, deployment, and
integrated test-environment validation is recorded.

## Consequences

- The reviewed rule behavior is reproducible and independent of the browser.
- A warning never blocks planning or changes an ICS-205 automatically.
- Zero warnings never means coordinated, interference-free, compatible, or operationally
  approved.
- Missing or inapplicable evidence stays visible without false precision.
- Approved revisions cannot retain the not-yet-determined classification.
- Different operational contexts may intentionally retain duplicate frequency pairs.
- Rule, threshold, hierarchy, or interpretation changes require a new version rather than
  changing retained evidence.

## Rejected alternatives

- Keeping provisional `RF-005` was rejected because missing frequencies can be valid for one-way,
  named-system, and multi-channel operations.
- Keeping provisional `RF-006` was rejected because candidate resources may legitimately be used
  for what-if coverage and availability planning before inclusion on an operational plan.
- Treating a missing area as a caution or conflict was rejected because overlap was not evaluated.
- Suppressing RF overlap findings because access codes differ was rejected because access codes
  do not provide RF isolation.
- Automatically applying changed source data or subscriber accommodations was rejected because
  practitioners must decide whether and how the plan changes.
