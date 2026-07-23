# ADR-0002: Identity, authorization, and audit boundaries

- Status: Accepted for P1.1 prototype
- Date: 2026-07-22
- Decision owners: Project maintainers

## Context

P1.1 requires protected accounts, configurable operational roles, incident-scoped access, and evidence of material changes. TX-COMU may later want membership information from CiviCRM, but the toolkit must remain independently deployable and must not share WordPress or CiviCRM tables, sessions, credentials, or availability dependencies.

## Decision

- Continue Django accounts and prototype tokens for the non-production P1.1 slice.
- Assign one installation role and optional incident memberships using the Administrator, COML, COMC, COMT, Contributor, and Read-only defaults.
- Resolve capabilities through `apps.accounts.policy`; API permissions and services are authoritative. The frontend only consumes returned capabilities to hide controls it cannot use.
- Scope non-administrator incident access through active memberships. New incident creators receive an incident membership automatically.
- Replace destructive incident and operational-period deletion with audited archival. Preserve material create, change, archive, membership, and import events in the append-only audit store.
- Keep `local` as the only enabled identity provider. Define a replaceable provider interface, but fail closed if an unimplemented provider is configured.

## Optional CiviCRM integration evaluation

If pursued, treat CiviCRM as an optional source of membership eligibility or profile attributes behind the provider interface. Do not query its database directly, reuse its password hashes or sessions, or make toolkit availability depend on WordPress. Prefer a standards-based identity provider with CiviCRM synchronization; otherwise use a narrowly scoped service account, stable external identifiers, explicit attribute mapping, short timeouts, cached last-known eligibility, revocation handling, and a local emergency-administrator path. A separate ADR and threat review are required before enabling it.

## Consequences

The prototype has centralized, testable authorization and audit behavior but token authentication still lacks federation, expiration, rotation, multifactor authentication, recovery controls, and production session management. Those remain P1.6 hardening work. Django admin records role changes in its administrative log; API changes also create toolkit audit events.
