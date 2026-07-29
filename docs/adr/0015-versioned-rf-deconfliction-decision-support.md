# ADR-0015: Versioned RF deconfliction decision support

- Status: Superseded by ADR-0021
- Date: 2026-07-28
- Issue: #39

## Context

This record preserves the original provisional contract for interpreting retained
`rf-deconfliction-v1-provisional` results. Practitioner review subsequently removed or
reclassified several provisional rules and introduced explicit operating classifications and
subscriber compatibility review. Current implementations follow
[ADR-0021](0021-practitioner-reviewed-rf-deconfliction.md).

An approved ICS-205 can contain co-channel, adjacent-channel, repeater-pair, naming, completeness,
or resource-omission conditions that deserve deliberate practitioner review. A warning engine
that changes silently, hides its inputs, treats squelch codes as isolation, or rewrites prior
results would weaken rather than support the communications-planning record.

The Toolkit must help a qualified practitioner find conditions worth reviewing without claiming
frequency-coordination, spectrum, incident-command, or regulatory authority.

## Decision

The Toolkit evaluates one approved ICS-205 revision and an explicit, optional selection of active
conventional-channel resources against the stable rule set identity
`rf-deconfliction-v1-provisional`. Rule logic remains outside the user interface and uses stable
identifiers:

- `RF-001` co-channel overlap;
- `RF-002` adjacent-channel overlap;
- `RF-003` reversed repeater pair;
- `RF-004` duplicate frequency pair under different names;
- `RF-005` missing receive or transmit frequency;
- `RF-006` selected active resource omitted from the approved revision; and
- `RF-007` missing approved operating or coordination area.

Co-channel and adjacent-channel rules compare transmit operating frequencies only when frozen
operational or coordination rings overlap. The provisional adjacent threshold is inclusive at
12,500 Hz. Ring overlap is inclusive when the WGS 84 center distance is equal to the combined
radii. CTCSS, DCS, NAC, and other squelch differences remain visible evidence and never suppress a
frequency warning.

Every warning preserves its rule ID and version, severity, compared inputs, evidence, assumptions,
plain-language explanation, and decision-support disclaimer. The analysis also retains:

- the exact approved revision identity and approval evidence;
- frozen assignment, frequency, squelch, source-resource, and approved-area inputs;
- the explicitly selected active-resource snapshots and release digests;
- the complete rule definitions and threshold;
- canonical input and result SHA-256 digests; and
- creator, approval, and timestamp evidence.

Analyses are immutable and retained. A changed plan, resource release, selected-resource set, or
rule version requires a new analysis. Approval fails closed until the exact rule-set version is
present in `ICT_APPROVED_DECONFLICTION_RULESETS` and both retained digests still validate.

## Consequences

- The interface may create and review a draft synthetic analysis before practitioner acceptance,
  but cannot approve it while the rule set remains unapproved.
- A warning is a review prompt, not proof of harmful interference. Zero warnings is not proof of a
  coordinated or interference-free plan.
- Missing area evidence produces its own warning rather than an invented location or assumed
  overlap.
- The first adjacent-channel threshold deliberately does not model receiver selectivity, emission
  masks, transmitter performance, site isolation, terrain, or propagation.
- Exact frequency, squelch, resource, and coordinate evidence inherits the incident and source
  classification. Audit detail records identifiers, counts, versions, and digests without copying
  that content.
- Qualified COML, COMT, COMC, and frequency-coordination practitioners must disposition every
  provisional rule, severity, threshold, assumption, boundary case, and explanation before the
  exact version may be approved for operational use.

## Rejected alternatives

- Implementing rule logic in the browser was rejected because direct API access could bypass it
  and deployed interfaces could disagree.
- Suppressing warnings when squelch values differ was rejected because squelch does not prevent RF
  energy or every interference condition.
- Comparing mutable current sites or library resources was rejected because later edits could
  change the meaning of an earlier result.
- Automatically approving or modifying an ICS-205 was rejected because coordination and incident
  decisions remain human responsibilities.
- Inventing a location or area for a missing snapshot was rejected because false precision would
  make the overlap result misleading.
