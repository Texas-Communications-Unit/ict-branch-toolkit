# ADR-0014: Disabled RadioReference provider contract

- **Status:** Accepted for synthetic contract development only
- **Date:** 2026-07-28
- **Issue:** #33

## Context

RadioReference approved a developer application for the ICT Branch Toolkit, but
that approval did not provide project-specific written terms for governmental or
nonprofit incident planning, multiuser web access, retention, caching, derived
works, display, controlled printing/export, redistribution, offline use,
attribution, termination, or deletion. The public repository must never contain
the developer key, individual-user credentials, or RadioReference-derived data.

The standard service is SOAP/XML. Directly coupling SOAP structures to the
frontend or existing resource models would make provider replacement difficult
and could bypass the Toolkit's versioned import, provenance, review, and audit
controls.

## Decision

The repository includes a server-side, provider-neutral synthetic contract named
`radioreference-normalized-v1-synthetic`. It provides:

- a disabled provider-status endpoint that never claims live availability;
- an HTTPS-only, non-secret WSDL configuration value;
- a bounded synthetic SOAP/XML parser that rejects DTD/entity declarations,
  malformed XML, non-SOAP envelopes, unexpected elements and attributes,
  duplicate source identifiers, oversized responses, and invalid numeric data;
- normalized agency, frequency, trunked-system, site, and talkgroup records;
- source identifier, source version, retrieval scope/time, and response digest
  provenance; and
- explicit evidence that raw responses and credentials were not retained.

`RADIOREFERENCE_ENABLED=true` records enablement intent only. It does not select
a live transport, load a developer key, accept user credentials, issue an
external request, cache data, import data, or enable export. Automated tests use
only obviously synthetic XML fixtures and explicit `synthetic:` scopes.

`ResourceSource.Type.RADIOREFERENCE` is reserved so a future approved import can
remain distinguishable from NIFOG, local, incident-created, and synthetic
sources. This change does not authorize or create a RadioReference release.

## Human gate for any live implementation

Before live work begins, maintainers must record:

1. written licensing terms covering the intended governmental/nonprofit and
   multiuser use;
2. permitted fields, query patterns, retention, caching, display, derived works,
   controlled exports, redistribution, attribution, deletion, and termination;
3. a security-reviewed individual Premium-account exchange that does not pool or
   retain credentials without express approval;
4. an outbound allowlist, bounded timeout/retry/rate controls, safe secret
   provisioning, rotation, disconnect, and kill-switch procedure;
5. review/diff and versioned import behavior that cannot overwrite approved local
   records; and
6. maintainer, security/privacy, and data-owner approval for the exact
   environment and implementation.

Live data must not be used to expand synthetic fixtures or be committed to the
public repository.

## Consequences

The Toolkit can validate normalization and XML safety without contacting
RadioReference or implying authorization. Local/manual and other approved
reference libraries remain fully usable. A future live adapter requires a new
decision record and code review; it cannot be enabled by configuration alone.
