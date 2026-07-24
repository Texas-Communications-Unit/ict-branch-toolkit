import hashlib

from .models import AuditEvent


def record_event(*, actor, action: str, target, details: dict | None = None) -> AuditEvent:
    return AuditEvent.objects.create(
        actor=actor,
        action=action,
        target_type=target._meta.label_lower,
        target_id=str(target.pk),
        details=details or {},
    )


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
