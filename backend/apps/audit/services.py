import hashlib
import json

from django.db import transaction

from .models import GENESIS_HASH, AuditEvent


def _chained_record_hash(
    *,
    previous_hash: str,
    sequence: int,
    actor,
    action: str,
    target_type: str,
    target_id: str,
    details: dict,
) -> str:
    """Hash this record together with the previous record's hash.

    Chaining each record's hash to its predecessor makes the log tamper-evident: retroactively
    editing, deleting, or reordering any past event changes its hash and every hash after it,
    so a chain-verification pass detects the break. ``occurred_at`` is intentionally excluded
    because it is assigned by the database on save and is not known before ``record_hash`` must
    be computed; ordering is instead guaranteed by the append-only ``sequence`` counter.
    """
    canonical = json.dumps(
        {
            "previous_hash": previous_hash,
            "sequence": sequence,
            "actor_id": actor.pk if actor else None,
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "details": details,
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def record_event(*, actor, action: str, target, details: dict | None = None) -> AuditEvent:
    details = details or {}
    target_type = target._meta.label_lower
    target_id = str(target.pk)
    with transaction.atomic():
        previous = AuditEvent.objects.select_for_update().order_by("-sequence").first()
        sequence = previous.sequence + 1 if previous else 0
        previous_hash = previous.record_hash if previous else GENESIS_HASH
        record_hash = _chained_record_hash(
            previous_hash=previous_hash,
            sequence=sequence,
            actor=actor,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details,
        )
        return AuditEvent.objects.create(
            actor=actor,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details,
            sequence=sequence,
            previous_hash=previous_hash,
            record_hash=record_hash,
        )


def verify_audit_chain() -> tuple[bool, "AuditEvent | None"]:
    """Recompute every record's hash in sequence order and confirm the chain is unbroken.

    Returns ``(True, None)`` when the whole chain verifies, or ``(False, event)`` for the
    first event whose stored ``record_hash``/``previous_hash`` does not match what is
    recomputed from its own fields and its predecessor's stored hash.
    """
    expected_previous_hash = GENESIS_HASH
    for event in AuditEvent.objects.order_by("sequence").iterator():
        if event.previous_hash != expected_previous_hash:
            return False, event
        recomputed = _chained_record_hash(
            previous_hash=event.previous_hash,
            sequence=event.sequence,
            actor=event.actor,
            action=event.action,
            target_type=event.target_type,
            target_id=event.target_id,
            details=event.details,
        )
        if recomputed != event.record_hash:
            return False, event
        expected_previous_hash = event.record_hash
    return True, None


def record_export(
    *,
    actor,
    action: str,
    revision,
    export_format: str,
    content: bytes,
    details: dict | None = None,
) -> AuditEvent:
    """Record an official export with the source revision, format, and a tamper-detection digest.

    The digest is computed over the exact bytes returned to the requester so that a later
    byte-for-byte comparison against this audit record can confirm a downloaded file was not
    altered after export.
    """
    return record_event(
        actor=actor,
        action=action,
        target=revision,
        details={
            "format": export_format,
            "content_sha256": hashlib.sha256(content).hexdigest(),
            "byte_size": len(content),
            "revision_number": revision.number,
            "revision_status": revision.status,
            **(details or {}),
        },
    )
