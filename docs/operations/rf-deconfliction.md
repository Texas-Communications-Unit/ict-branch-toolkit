# RF deconfliction decision support

Issue #39 provides explainable, retained RF planning decision support. It does not provide
frequency coordination, spectrum authorization, an interference determination, a propagation
study, ICS-205 approval, or operational approval.

## Safe default and activation gate

The implemented rule set is:

```text
rf-deconfliction-v2-reviewed
```

`ICT_APPROVED_DECONFLICTION_RULESETS=[]` permits authorized users to create and review draft
analyses but prevents application approval. Keep that default until all local and CI tests pass,
the migration is exercised against the shared test database, the deployed interface is checked,
and the integrated acceptance matrix below is recorded.

Only after those gates are satisfied may an administrator set:

```text
ICT_APPROVED_DECONFLICTION_RULESETS=["rf-deconfliction-v2-reviewed"]
```

That setting permits approval of a retained result. It does not give the result operational or
regulatory authority.

## Assignment preparation

Every assignment must explicitly identify its operating classification:

| Classification | Intended use |
| --- | --- |
| Fixed pair | Conventional assignment with receive and transmit frequencies |
| Broadcast/transmit-only | One-way transmitter; the user confirms this intent during entry |
| Receive-only | One-way receiver; the user confirms this intent during entry |
| Named system | Trunked, LTE/5G, SCADA, spread-spectrum, or other named service |
| Dynamic/multi-channel pool | A system selecting from multiple possible channels |
| Not yet determined | Draft planning only; approval is blocked |

Do not invent a missing frequency, coordinate, area, access code, or classification. A candidate
resource being considered for coverage or availability may remain in planning without appearing
on the approved ICS-205.

## Analysis workflow

1. Select an active incident and an approved ICS-205 revision.
2. Review the frozen assignment classifications, versioned comparison sources, and approved
   site-area evidence.
3. Create a new immutable analysis.
4. Review warnings and every not-applicable or not-evaluated status. Zero warnings does not mean
   the plan is conflict-free or compatible.
5. Record any finding disposition. Dispositions are append-only and do not modify the plan.
6. If the plan or any frozen source, site area, classification, rule, or threshold changes, create
   a new analysis and retain the earlier result.
7. Approve only when the exact rule version is allowlisted and the result has received the
   applicable human review.

Only frozen operational and coordination rings are used. A boundary touch counts as overlap.
Missing area evidence produces `RF-007` “Area overlap not evaluated.” Access-code differences
remain evidence and never suppress an RF overlap warning.

## Reviewed rule and status register

| ID | Condition | Result |
| --- | --- | --- |
| `RF-001` | Equal transmit frequencies and overlapping approved areas | Critical, nonblocking |
| `RF-002` | Non-equal transmit frequencies separated by 12,500 Hz or less and overlapping approved areas | Warning, nonblocking |
| `RF-003` | Fixed-pair receive/transmit values are inverse between assignments | Critical, nonblocking |
| `RF-004` | Different names use the same non-null fixed pair | Warning, nonblocking |
| `RF-008` | Directional access code differs from the authoritative selected source | Critical, nonblocking |
| `RF-007` | No frozen approved area exists | Not evaluated |
| `RF-STATUS-001` | Fixed-frequency rule does not apply to the classification | Not applicable |
| `RF-STATUS-002` | Authoritative expected access-code evidence is unavailable | Not evaluated |

For `RF-008`, the selected versioned channel definition has priority over an explicitly selected
approved subscriber programming profile. Receive is compared only with receive; transmit is
compared only with transmit. A one-way assignment evaluates only its applicable operating
direction. Unknown expected values remain not evaluated.

## Required synthetic acceptance matrix

All examples must use clearly synthetic frequencies, names, access codes, coordinates, sites, and
incidents.

| Rule or status | Positive/boundary case | Negative or unavailable case |
| --- | --- | --- |
| `RF-001` | Equal TX with overlap, including exact area-boundary touch, produces one critical finding even when access codes differ | Equal TX without overlap produces no `RF-001` |
| `RF-002` | Non-equal TX separated by 12,499 Hz or exactly 12,500 Hz with overlap produces one warning | 12,501 Hz separation or no overlap produces no `RF-002` |
| `RF-003` | A non-simplex fixed pair exactly inverse to another produces one critical finding | A partial match or non-fixed classification produces no `RF-003` |
| `RF-004` | Different names with the same non-null fixed pair produce one warning | The same name, different pair, or non-fixed classification produces no `RF-004` |
| `RF-008` | Directional normalized text differs from the authoritative source and produces one critical finding with provenance | Matching values produce no finding; missing authoritative direction produces `RF-STATUS-002` |
| `RF-007` | Missing approved area produces a not-evaluated status | An approved operational or coordination area permits overlap evaluation |
| Operating intent | Transmit-only, receive-only, named-system, and dynamic-pool assignments retain explicit intent without a missing-value finding | Not-yet-determined blocks revision approval |

## Complete environment validation

Before operational allowlisting, record:

- backend formatting, lint, Django checks, migration drift, OpenAPI validation, and the complete
  backend test suite;
- frontend formatting, lint, type checking, unit/component tests, production build, and the
  complete Playwright browser suite using Node.js 24;
- PostgreSQL/PostGIS migration and service health in the shared test environment;
- authenticated creation from an approved incident-scoped revision and denial for cross-incident,
  unapproved, unauthorized, update, and delete attempts;
- all synthetic positive, negative, and exact-boundary cases above;
- accessible text for severity, rule, status, assumptions, explanation, provenance, and
  disclaimer without relying on color or the map;
- deterministic input/result digests, tamper rejection, retained v1 history, immutable analyses,
  append-only dispositions, and the audit-chain events;
- no sensitive frequency, access-code, coordinate, source snapshot, warning explanation, or
  disposition explanation copied into audit details; and
- backup confirmation, deployed commit identity, clean server worktree, container/service health,
  and public endpoint behavior after an authorized deployment.

If any check fails, keep the version out of the allowlist, retain sanitized evidence, and correct
the implementation before operational use.
