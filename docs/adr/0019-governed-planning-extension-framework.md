# ADR-0019: Governed planning-tool and report extension framework

- **Status:** Accepted for synthetic contract validation only
- **Date:** 2026-07-28
- **Issue:** #24
- **Depends on:** ADR-0018 / Issue #23

## Context

Additional ICT Branch tools and reports need a stable boundary that does not
place unrelated workflows inside the ICS-205 implementation. The boundary must
not become an arbitrary code-upload mechanism, bypass incident authorization,
or imply that a generated artifact is an official form or approval.

Every future operational extension needs its own qualified human review of
requirements, authority, source records, data classification, retention,
approval behavior, accessibility, and acceptance evidence. This ADR authorizes
only the framework and its explicitly synthetic example.

## Decision

### Code-defined registry

Extensions are server code reviewed and shipped with the application. The
registry contains no upload, package-install, dynamic-import, shell-command, or
remote-code path. A manifest declares:

- stable key, semantic version, provider, and extension contract version;
- tool and/or report capabilities, scope, required permission, inputs,
  outputs, validation, audit, and deterministic export behavior;
- source record types, approval requirements, sensitivity, retention, failure
  isolation, accessibility behavior, and whether output can be official.

The initial server supports contract `1.0`. A request must name the exact
contract, extension, and capability. Unknown or incompatible versions fail
closed with operator-facing recovery language.

### Installation and enablement

A code-defined extension remains unavailable until an Administrator explicitly
installs its exact registry manifest and then enables it. Installation records
the complete manifest and SHA-256 digest and starts disabled. Enablement fails
if the installed version, contract, or digest no longer matches the registry.
Install, enable, and disable actions are append-only audit events. Installation
history cannot be deleted through the model.

### Execution and retention

Runs require `extension.run` within the current incident and an approved
same-incident ICS-205 revision. Contributor and Read-only roles can see
authorized incident output but cannot run extensions. Administrator, COML,
COMC, and COMT can run; only Administrator can manage installation state.

Each run retains:

- incident and approved source revision;
- extension, capability, kind, and exact versions;
- canonical input/result snapshots and SHA-256 digests;
- output classification, actor, timestamp, and bounded failure state.

Runs are immutable and retained with the incident. General audit events retain
identifiers, versions, classifications, and digests rather than copying source
or result content. The deterministic JSON package is built only from retained
versioned evidence and is audited on every export.

### Failure isolation

An extension is invoked only through its dedicated endpoint. It receives the
approved source revision as read-only input and has no contract method for
altering it. A handler failure creates bounded retained failure evidence,
returns `503` for that optional run, and does not change core incident,
ICS-205, collaboration, approval, or export records.

### Synthetic example

`synthetic-readiness-summary` is the only initial registry entry. It provides a
small tool and report over approved ICS-205 assignment metadata and counts. It
does not expose frequencies or protected contact fields and always classifies
output as `decision_support`. Its purpose is to validate registry,
authorization, audit, retention, deterministic packaging, failure isolation,
accessibility, backup, and test contracts—not to establish an operational
readiness standard.

## Consequences

Future extensions require reviewed application code and a new human gate; they
cannot be introduced by uploading executable content. Extension versions can
evolve independently while the contract version protects callers from silent
schema changes.

The initial executor is synchronous. It is bounded by the request serializer
and example workload but does not establish production concurrency or duration
targets. Long-running future tools require a separately reviewed job boundary,
resource limits, cancellation, and recovery design.

No extension in this slice can produce an official output. An official
classification requires explicit authority, form requirements, approval
workflow, retention, and qualified acceptance criteria in a separate issue.
