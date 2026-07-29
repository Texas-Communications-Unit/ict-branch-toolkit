# ADR-0020: Defer live RadioReference access behind a separate authorization gate

- Status: Accepted
- Date: 2026-07-29
- Decision owners: Maintainers
- Related issue: #33
- Live follow-up: #75

## Context

The merged RadioReference work provides a disabled, network-free synthetic
contract. It proves bounded SOAP/XML parsing, provider-neutral normalization,
provenance, and safe failure behavior without using a developer key, individual
credentials, or provider data.

RadioReference approved the ICT Branch Toolkit developer application. The
project administrator accepts the published individual-account and Premium
subscription requirements. Current public guidance nevertheless describes the
standard API as intended for radio programming and radio-adjacent tools and
directs most other uses to a paid license. The repository does not contain
project-specific written language covering incident-planning retention, mapping,
controlled ICS-205 use, exports, or multiuser operation.

Issue #33 also accumulated detailed operational requirements that should not be
lost merely because live activation remains externally gated.

## Decision

Treat the disabled synthetic provider contract as the completed evaluation and
architecture result. Track live transport, credential exchange, incident import,
and shared-deployment activation in follow-up Issue #75.

Any future live implementation must retain these approved requirements:

1. **Individual access:** Each live user supplies an individual RadioReference
   account with an active Premium subscription. Accounts and credentials are
   never pooled, shared, placed in GitHub, retained in the Toolkit database,
   written to browser storage, embedded in frontend assets, or logged.
2. **Volatile sessions:** RadioReference credentials exist only in protected
   server memory for the current authenticated Toolkit session and device. They
   are cleared on logout, Toolkit session expiry, provider authentication
   failure, disconnect, or process/session loss. A separate Toolkit session or
   device requires a separate RadioReference login.
3. **Explicit online search:** Opening the RadioReference workspace never
   performs a query. The initial search requires a state, permits an optional
   county, and runs only after the user selects **Search**. No scraping, bulk
   download, mirroring, background refresh, or general provider cache is
   permitted.
4. **Deliberate incident retention:** Only records deliberately selected by a
   user with `plan.edit` authority may be normalized and saved to an incident.
   Raw SOAP responses and credentials are not retained. Saved records remain
   available to authorized incident users without RadioReference
   reauthentication and follow the complete incident records-retention and
   legal-hold lifecycle.
5. **Provenance and revision history:** Retain the immutable original import
   snapshot, provider source identifier, retrieval time, importing actor, query
   scope, and applicable version metadata. Edits create incident-local
   revisions; removal is soft removal or supersession. Provider changes may
   create a notice, but updates are never applied automatically.
6. **Source-aware interface:** Provide a full-page internal RadioReference
   workspace and distinct source selectors for RadioReference, NIFOG, AUXFOG,
   state SCIP resources, and local or incident data. Internal displays retain
   source attribution. The official ICS-205 layout is not altered merely to add
   provider attribution; provenance remains in internal records.
7. **Coordinates:** Never invent or infer a location. Preserve all supplied
   coordinate sources and apply the default priority: FCC ASR, explicit user
   input, then RadioReference. An authorized incident editor may override the
   priority only with a reason and an audit event.
8. **Copy from previous plan:** An authorized user may copy selected or complete
   communications content from an exact prior revision into an independent new
   draft. The workflow requires source-view and destination-edit authority,
   preserves lineage, excludes old incident identity, dates, personnel,
   approvals, and signatures, and prompts **Merge**, **Replace current draft**,
   or **Cancel** whenever destination content exists. Apparent duplicates
   produce only a non-blocking warning.
9. **Audit and output integrity:** Credential-safe audit events cover connection,
   authentication failure, query scope/result count, selection, save, retained
   access, map or plan use, export, update review, revision, supersession, and
   coordinate override. Every generated ICS-205 or map export remains tied to an
   exact plan revision, generating user, generation time, and file checksum.
10. **Activation gate:** Before any live request, maintainers must record the
    written permission or license covering this use, approve the security and
    privacy design, provision the developer key through protected server-side
    secrets, approve the exact environment, and authorize a credential-safe
    live test. `RADIOREFERENCE_ENABLED=false` remains the immediate kill switch.

## Consequences

- Issue #33 can close after its decision record is merged without representing
  live RadioReference access as implemented or licensed.
- The approved workflow and retention requirements remain reviewable in source
  control rather than only in an issue discussion.
- No developer key, user credential, live endpoint call, or real provider record
  is introduced by this decision.
- A future implementation starts from an explicit contract and external
  authorization checklist instead of reopening settled product decisions.

## Alternatives considered

- **Implement live access under the standard public API terms:** Rejected because
  the public guidance does not clearly authorize the Toolkit's retention,
  incident-planning, mapping, and controlled-export use.
- **Keep all future requirements only in Issue #33:** Rejected because issue
  closure would make approved design decisions difficult to discover and audit.
- **Drop RadioReference support entirely:** Rejected because the approved
  developer application and synthetic provider boundary remain useful once the
  external authorization gate is satisfied.
