# Prototype Threat Assumptions

## Assets

Assets include approved communications plans, source/version provenance, user authority,
audit history, site coordinates, versioned RF inputs, subscriber profiles, calculation methods,
approval snapshots and digests, exports, and configuration. The prototype permits synthetic data
only.

## Primary threats

- Unauthorized reading or alteration of drafts and approved information.
- A UI-only control being bypassed through direct API access.
- Secrets or operational data entering source control, logs, fixtures, or screenshots.
- Published information losing its source, approval, or revision linkage.
- Malicious imports, file uploads, map styles, or external integrations.
- Dependency or container compromise.
- Planning warnings being interpreted as technical or legal authorization.
- A modeled RF assumption, provisional range, or subscriber profile being presented as a recorded
  fact or approved operational default.
- An explicit unknown being replaced with zero or a hidden default, creating false precision.
- Transmitter output power being mislabeled as ERP/EIRP or an antenna gain reference being omitted.
- AGL, AMSL, and HAAT being conflated or silently derived with an unapproved terrain method.
- A mutable input/profile change rewriting the meaning of an approved calculation.
- Cross-incident access to RF inputs, profiles, snapshots, or sensitive equipment/site details.
- An unapproved elevation provider receiving incident coordinates or returning misleading terrain.
- Stale, partial, missing, or out-of-coverage terrain being presented as complete.
- Vertical-reference or datum conversion being omitted while apparently precise elevations remain.
- Retry or cache refresh rewriting the source evidence behind an earlier HAAT result.
- A SOAP/XML response using DTDs, entities, unexpected schema content, excessive
  size, or invalid numeric fields to consume resources or bypass normalization.
- A developer key or individual RadioReference credential reaching the browser,
  logs, build layers, audit payloads, fixtures, exports, or pooled storage.
- A configuration flag being mistaken for licensing approval or live-provider
  readiness.
- Exact coordinates being retained when an operator intended generalization or redaction.
- Mutable observations, reviews, or fitted sets erasing unfavorable field evidence.
- Cross-incident RF snapshots or analysis results being attached to an observation.
- Observer/source text, notes, locations, or measurements leaking through audit detail or exports.
- Missing values or outliers being silently removed from calibration.
- An incident-local fit overwriting an organization default or being represented as validated
  coverage.
- A browser-only or mutable deconfliction rule producing results that cannot be reconstructed.
- Squelch differences suppressing a co-channel or adjacent-channel warning.
- A missing operating area being replaced with an invented location or assumed non-overlap.
- A provisional warning, severity, threshold, or zero-warning result being represented as
  coordination, spectrum, propagation, or incident-command authority.
- Frequencies, squelch values, coordinates, frozen site evidence, selected resources, or warning
  contents leaking through deconfliction audit details.
- A browser-selected or unapproved terrain provider receiving incident path coordinates.
- A coarse source being sampled below its declared resolution and presented with false precision.
- Missing, boundary, out-of-coverage, or unsupported terrain being presented as a complete path.
- A terrain result silently replacing the Phase 2 estimate or being represented as diffraction,
  propagation, field validation, coordination, regulatory, or coverage-guarantee evidence.
- Provider exception detail, credentials, coordinates, samples, or raw responses leaking through
  API failures, audit events, logs, screenshots, or CI artifacts.
- Repeated maximum-size synchronous terrain requests exhausting application resources.

## Design responses

Enforce policy in the backend, keep approved revisions immutable, retain provenance, use
append-only audit design, validate imports before persistence, isolate external integrations, scan
dependencies/secrets/containers, and label limitations at user and export boundaries. The P1.6
[append-only audit review](audit-abuse-cases.md) records formal audit abuse cases, automated
evidence, and the limits of the local hash chain. Other surfaces must add corresponding abuse
cases and security tests as they are implemented.

For P2.1, use typed canonical units; preserve transmitter power, losses, antenna gain/reference,
and every ERP derivation step; distinguish isotropic and dipole gain references; keep AGL, AMSL,
and HAAT separate; represent unknown values explicitly; and create immutable canonical RF input
snapshots and digests from approved profile versions. P2.2 HAAT calculations bind to the exact
approved snapshot. Version-level `input_basis` distinguishes
`recorded_fact`, `modeled_assumption`, `mixed`, and `unknown`; mixed versions use minimized notes to
explain the boundary. The current contract does not claim per-field provenance.

Every RF input, profile, and snapshot operation must enforce incident scope in backend policy and
create a non-sensitive append-only audit event. No numerical range, default subscriber assumption,
terrain method, or calculation convention is operationally approved until qualified COML, COMT,
COMC, and RF engineering reviewers complete the
[ADR-0008 human gate](../adr/0008-versioned-rf-analysis-inputs-and-subscriber-profiles.md).
Calculated output remains planning decision support, not propagation or coordination authority.

For P2.2, provider selection is server-controlled and exact source descriptors must be
allowlisted before retrieval. The safe default makes no external request. Exact query/sample
snapshots, source and result digests, cache state, transformation metadata, exclusions, warnings,
and method versions are retained. Cache refresh and retry create new immutable evidence. Incident
policy scopes every HAAT result and its elevation snapshot; audit events identify material actions
without duplicating coordinates, RF values, or terrain samples in audit detail. Partial and
unavailable results cannot be approved. See
[ADR-0009](../adr/0009-source-aware-elevation-and-reproducible-haat.md).

The RadioReference contract remains network-free and unavailable regardless of
the feature flag. It accepts only bounded, explicitly synthetic SOAP fixtures,
rejects DTD/entity and unexpected schema content, normalizes allowlisted fields,
and records a response digest without retaining raw XML or credentials. A live
adapter, credential exchange, cache, import, or export requires a new reviewed
implementation after the
[licensing and security gate](../operations/radioreference-provider.md).

For P2.5, coordinate generalization or redaction occurs before persistence. Observations,
corrections, review decisions, calibration sets, and set membership are retained as immutable
evidence. The backend validates incident scope and exact approved RF/analysis sources. Calibration
records every selected input, missing/outlier exclusion, parameter, comparison metric, warning,
and digest while omitting coordinates, observer/source text, and notes from its result snapshot.
Audit detail contains action metadata and digests rather than field content.

The provisional method remains fail-closed for approval until its exact version is allowlisted.
Every recommendation remains marked incident-local and not promoted. Non-synthetic collection
requires separate incident authority, security/privacy review, retention/consent decisions, and
qualified RF review. See
[ADR-0012](../adr/0012-field-observations-and-incident-local-calibration.md).

For P2.6, the backend rejects cross-incident or internally inconsistent source
chains and recalculates retained digests before approval/export. Append-only
review changes and elevation expiration mark completed evidence stale rather
than silently recalculating it. Approval uses an exact-version server
allowlist; export requires both RF approval and plan-export authority. Export
audit details contain digest, size, version, and action metadata rather than
plan contacts, observation locations, source text, or notes.

Residual risks include database administrators bypassing model-level
immutability, denial of service through repeated synchronous work, protected
information remaining in minimized model/dataset evidence, local bearer-token
limits, and the absence of external audit anchoring. General API throttling,
incident scope, bounded upload verification, protected database access,
backup/recovery controls, and human gates reduce but do not eliminate these
risks. See
[ADR-0016](../adr/0016-phase-2-validation-evidence-bundles.md).

For RF deconfliction, versioned rules run only on the backend against an approved incident-scoped
ICS-205 revision, frozen approved areas, and an explicit active-resource selection. The service
never invents a missing location and never uses a squelch difference to suppress a frequency
warning. It retains canonical input/result snapshots and digests; later changes create a new
analysis rather than rewriting evidence. Approval fails closed until the exact rule version passes
qualified review. Audit details retain only identifiers, versions, counts, and digests rather than
frequency, squelch, coordinate, site, resource, or warning content. See
[ADR-0015](../adr/0015-versioned-rf-deconfliction-decision-support.md).

For P3.1, provider and engine selection remain server-controlled and the
disabled provider is the default. The exact source/dataset/content digest and
engine/version must match the protected allowlist before a provider is called.
Requests are incident-scoped and bounded by distance and sample count. Input
and result evidence is immutable; retry creates lineage and configuration or
Phase 2 changes make old evidence stale. Missing/out-of-coverage samples are
not interpolated, and only a current complete result can be approved.

The UI and result snapshot keep Phase 2 and terrain values separate, label the
sampled method's unsupported conditions, and provide text-distinct profile
states. Provider failures return bounded recovery language while protected
server logs hold exception detail. Audit events retain identifiers, versions,
states, and digests rather than coordinates, samples, RF values, or
credentials. General throttling and profile bounds reduce but do not eliminate
synchronous denial-of-service risk. See
[ADR-0017](../adr/0017-optional-source-aware-terrain-analysis.md).
