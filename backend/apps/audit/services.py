from .models import AuditEvent


def record_event(*, actor, action: str, target, details: dict | None = None) -> AuditEvent:
    return AuditEvent.objects.create(
        actor=actor,
        action=action,
        target_type=target._meta.label_lower,
        target_id=str(target.pk),
        details=details or {},
    )
