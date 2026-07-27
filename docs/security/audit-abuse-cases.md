# Append-only audit review and abuse cases

- Status: P1.6 audit slice review complete
- Review date: 2026-07-27
- Scope: application audit events, hash-chain verification, export-digest verification, and
  incident-scoped API mutations

This review uses synthetic test records only. It does not authorize non-synthetic data, hosted
testing, deployment, or production use.

## Review result

Material API mutations and their audit append now share the request database transaction. If an
unexpected exception prevents the audit event from being written, the API returns a generic
server error and rolls back the data change. Known API validation, permission, and throttle
errors also mark the transaction for rollback.

Audit events remain append-only through supported model and queryset mutation paths. Actor
foreign keys use protective deletion, administrator add/change/delete actions are disabled, and
hash-chain verification checks sequence continuity, predecessor linkage, and the canonical
record hash. Protected assignment contact values are excluded from audit details; the event
records only the changed field names.

Export verification accepts only a 64-character hexadecimal SHA-256 digest or an uploaded file.
The server-derived digest, byte count, format, revision number, and revision status cannot be
overridden by caller-supplied audit details. A digest match is bound to the recorded revision and
export format.

## Automated abuse cases

| Abuse case | Expected control | Automated evidence |
| --- | --- | --- |
| Unauthenticated client sends a direct mutation request | Request is denied; target and audit log remain unchanged | `test_unauthenticated_mutation_is_denied_without_a_success_audit_event` |
| Authenticated user guesses an object identifier outside assigned incidents | Scoped lookup returns not found; no mutation or success event is recorded | `test_cross_incident_mutation_is_hidden_and_does_not_poison_the_audit_log` |
| Audit append fails after a material serializer save | The request transaction rolls back the data change and returns a generic error | `test_audit_append_failure_rolls_back_the_material_api_mutation` |
| Protected contact values are submitted in an assignment update | Audit details contain field names, not submitted values | `test_protected_assignment_values_are_not_copied_into_audit_details` |
| Application code tries to save, update, bulk update, or delete an audit row | Supported ORM mutation paths raise the append-only guard | `test_application_orm_cannot_rewrite_or_remove_an_audit_event` |
| Account deletion would erase actor attribution | Database protection blocks deletion of the attributed actor | `test_deleting_an_actor_cannot_erase_audit_attribution` |
| A caller tries to override server-derived export metadata | Server digest, size, format, and revision fields take precedence | `test_export_audit_callers_cannot_override_authoritative_digest_metadata` |
| A valid digest is replayed against another revision or format | Verification reports no match | `test_export_digest_replay_is_bound_to_the_original_revision_and_format` |
| A malformed digest is submitted | Validation rejects it before audit lookup | `test_verify_rejects_a_malformed_digest` |
| A stored event is rehashed with a non-contiguous sequence | Full-chain verification reports the first broken event | `test_verify_audit_chain_detects_a_rehashed_sequence_gap` |

The broader audit-chain, authorization, export-integrity, and resource-import tests remain part of
the required backend suite.

## Operational verification

Run full-chain verification after restore, upgrade, rollback, suspected database manipulation,
and at the interval set by adopted policy:

```console
python manage.py shell -c "from apps.audit.services import verify_audit_chain; ok, event = verify_audit_chain(); print('OK' if ok else f'BROKEN at {event.pk}'); raise SystemExit(0 if ok else 1)"
```

A nonzero result is an integrity incident. Preserve the database and application logs, restrict
write access, compare against a known-good backup or independent checkpoint, and follow the
organization's incident-response process. Do not repair or delete the first broken record before
evidence is preserved.

## Explicit limitations and human gates

- The SHA-256 chain is tamper-evident, not tamper-proof. It uses no signing key. A sufficiently
  privileged database attacker can recompute a modified chain, forge a new tail, truncate the
  tail, or remove the whole table. Detection of those cases requires protected backups or an
  independent off-system checkpoint.
- The application audit log records successful material actions. Denied and failed attempts are
  not written as successful `AuditEvent` records. Operators must retain and monitor protected
  reverse-proxy, authentication, and application logs for those attempts.
- Request-wide database transactions add overhead. Representative P1.6 performance tests must
  include authenticated write paths before a release candidate is accepted.
- No tamper-evident remote audit export, cryptographic signature, security information and event
  management integration, or adopted incident-data retention schedule is implemented.
- Security and operational acceptance, maintainer review, and synthetic-data-only restrictions
  remain mandatory before any hosted test uses non-synthetic data.
