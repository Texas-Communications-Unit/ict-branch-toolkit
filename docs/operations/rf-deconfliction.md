# RF deconfliction decision support

Issue #39 adds synthetic-only, explainable RF deconfliction decision support. It does not provide
frequency coordination, spectrum authorization, interference protection, propagation analysis,
or an ICS chain-of-command decision.

## Safe default and human gate

`ICT_APPROVED_DECONFLICTION_RULESETS=[]` permits creation and review of draft synthetic analyses
but prevents approval. The only included rule set is:

```text
rf-deconfliction-v1-provisional
```

Before an installation may add that exact value to the allowlist, qualified COML, COMT, COMC, and
frequency-coordination practitioners must review and record a disposition for every rule,
severity, threshold, assumption, explanation, positive case, negative case, and boundary case.
Security and data owners must separately approve the proposed environment and data classification.

If those gates are recorded, the exact version can be enabled with:

```text
ICT_APPROVED_DECONFLICTION_RULESETS=["rf-deconfliction-v1-provisional"]
```

That setting permits application approval of a retained result. It does not convert the result
into coordination or operational authority.

## Analysis workflow

1. Select an active incident and an approved ICS-205 revision.
2. Review the frozen assignment and approved site-area evidence in that revision.
3. Optionally select active conventional-channel resources that should be checked for omission.
   The engine does not assume that every library resource belongs in every plan.
4. Create a new immutable analysis.
5. Review the exact rule-set version, threshold, compared inputs, evidence, assumptions,
   explanation, input digest, and result digest.
6. Resolve each warning through the applicable planning and coordination process outside the
   engine. Do not edit an approved plan automatically.
7. If the plan, site areas, selected resources, source release, or rule set changes, create a new
   analysis and retain the earlier result.
8. Approve an analysis only when the exact rule version passed the human gate and the result has
   received the required incident review.

Only frozen operational and coordination rings are used for overlap. A missing area produces
`RF-007`; the engine never invents a location. A boundary touch counts as overlap. Squelch values
are displayed as evidence but never suppress a warning.

## Provisional rule register

| Rule ID | Provisional condition | Severity | Required reviewer disposition |
| --- | --- | --- | --- |
| `RF-001` | Equal transmit frequencies and overlapping approved areas | Critical | Pending |
| `RF-002` | Non-equal transmit frequencies separated by 12,500 Hz or less and overlapping approved areas | Warning | Pending |
| `RF-003` | Receive/transmit pairs are reversed between assignments | Critical | Pending |
| `RF-004` | Different channel names use the same non-null receive/transmit pair | Warning | Pending |
| `RF-005` | Receive or transmit frequency is missing | Caution | Pending |
| `RF-006` | A user-selected active conventional resource is absent from the approved revision | Warning | Pending |
| `RF-007` | An assignment has no frozen operational or coordination ring | Caution | Pending |

Reviewers must record the accepted or revised severity, rule wording, evidence requirements,
operational assumptions, and rationale. Any logic-affecting revision requires a new version rather
than changing the meaning of retained results.

## Domain review test table

All examples must use clearly synthetic frequencies, names, coordinates, sites, incidents, and
resources. “Warning” below means the expected rule result, not an authorization decision.

| Rule | Case type | Synthetic condition | Expected result |
| --- | --- | --- | --- |
| `RF-001` | Positive | Equal transmit frequencies; approved rings overlap | One critical `RF-001` |
| `RF-001` | Negative | Equal transmit frequencies; approved rings do not overlap | No `RF-001` |
| `RF-001` | Boundary | Center distance equals combined radii | One critical `RF-001` |
| `RF-001` | Squelch | Equal transmit frequencies and overlapping rings; squelch differs | `RF-001` remains and records the difference |
| `RF-002` | Positive | Separation is 12,499 Hz; approved rings overlap | One warning `RF-002` |
| `RF-002` | Negative | Separation is 12,501 Hz; approved rings overlap | No `RF-002` |
| `RF-002` | Boundary | Separation is exactly 12,500 Hz; approved rings overlap | One warning `RF-002` |
| `RF-002` | Area negative | Separation is within threshold; rings do not overlap | No `RF-002` |
| `RF-003` | Positive | First RX/TX equals second TX/RX and the pair is not simplex | One critical `RF-003` |
| `RF-003` | Negative | Only one side of the pair matches | No `RF-003` |
| `RF-004` | Positive | Different names and identical non-null RX/TX pairs | One warning `RF-004` |
| `RF-004` | Negative | Same name and identical pair | No `RF-004` |
| `RF-005` | Positive | RX or TX is null | One caution `RF-005` naming every missing field |
| `RF-005` | Negative | RX and TX are both present | No `RF-005` |
| `RF-006` | Positive | A user-selected active resource is absent from assignments | One warning `RF-006` |
| `RF-006` | Negative | The selected resource is linked to an assignment | No `RF-006` |
| `RF-007` | Positive | No frozen operational or coordination ring exists | One caution `RF-007` |
| `RF-007` | Negative | At least one valid frozen operational or coordination ring exists | No `RF-007` |

## Required review record

The human-review record must identify:

- exact commit and `rf-deconfliction-v1-provisional` version;
- reviewer names, roles, qualifications, organizations, and dates;
- each test-table result and any additional practitioner scenario;
- accepted or rejected rule, severity, threshold, evidence, and explanation decisions;
- unresolved limitations and the environment/data scope accepted for evaluation;
- security and privacy disposition;
- approval authority and effective date; and
- the required version change when any reviewed behavior changes.

Attach the record through the project’s controlled review process. Do not place sensitive incident,
frequency, site, credential, or practitioner personal data in a public issue or test artifact.

## Verification

For an approved synthetic evaluation, confirm:

- a draft analysis can be created only from an approved revision in the selected active incident;
- assignments from another incident and unapproved revisions fail;
- rule IDs, versions, severities, compared inputs, evidence, assumptions, explanations, and the
  disclaimer appear in both API and accessible interface output;
- the 12,500 Hz and area-touch boundaries are inclusive;
- a squelch difference remains visible and does not suppress `RF-001` or `RF-002`;
- active resources are checked only when the user explicitly selects them;
- identical inputs produce the same input and result digests;
- the retained record cannot be updated or deleted;
- approval fails with the default empty allowlist and succeeds only for the exact approved version;
- changed retained input or result evidence fails digest verification; and
- audit details contain no frequencies, squelch values, coordinates, site snapshots, or warning
  contents.

If any check fails, keep the version out of the allowlist, retain sanitized evidence, and return
the implementation to maintainers and qualified reviewers.
