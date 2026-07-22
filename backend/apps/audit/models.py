import uuid

from django.conf import settings
from django.db import models


class AppendOnlyQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise RuntimeError("Audit events are append-only.")

    def delete(self):
        raise RuntimeError("Audit events are append-only.")


class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="audit_events"
    )
    action = models.CharField(max_length=80)
    target_type = models.CharField(max_length=120)
    target_id = models.CharField(max_length=80)
    details = models.JSONField(default=dict)
    occurred_at = models.DateTimeField(auto_now_add=True)

    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        ordering = ["-occurred_at"]

    def __str__(self) -> str:
        return f"{self.occurred_at}: {self.action} {self.target_type}:{self.target_id}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("Audit events are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Audit events are append-only.")
