import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

from apps.incidents.models import Incident

sha256_validator = RegexValidator(
    r"^[0-9a-f]{64}$",
    "Enter a lowercase SHA-256 digest.",
)


class OfflinePackage(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        LOCKED = "locked", "Locked"
        EXPIRED = "expired", "Expired"
        REVOKED = "revoked", "Revoked"
        PURGED = "purged", "Purged"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.ForeignKey(
        Incident,
        related_name="offline_packages",
        on_delete=models.PROTECT,
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="offline_packages",
        on_delete=models.PROTECT,
    )
    device_id = models.UUIDField()
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    scope = models.JSONField(default=dict)
    payload_snapshot = models.JSONField(default=dict)
    manifest = models.JSONField(default=dict)
    manifest_sha256 = models.CharField(max_length=64, validators=[sha256_validator])
    revision_state = models.JSONField(default=dict)
    last_sequence = models.PositiveIntegerField(default=0)
    last_chain_sha256 = models.CharField(max_length=64, validators=[sha256_validator])
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    purged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["incident", "requested_by", "status"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.incident}: offline package {self.id}"

    def delete(self, *args, **kwargs):
        raise ValidationError("Offline package evidence is retained; use controlled purge.")


class OfflineMutationReceipt(models.Model):
    class Status(models.TextChoices):
        APPLIED = "applied", "Applied"
        CONFLICT = "conflict", "Conflict"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, editable=False)
    package = models.ForeignKey(
        OfflinePackage,
        related_name="mutation_receipts",
        on_delete=models.PROTECT,
    )
    sequence = models.PositiveIntegerField()
    actor_id_snapshot = models.PositiveBigIntegerField()
    device_id = models.UUIDField()
    operation = models.CharField(max_length=40)
    object_id = models.UUIDField(null=True, blank=True)
    revision_id = models.UUIDField()
    previous_hash = models.CharField(max_length=64, validators=[sha256_validator])
    payload_sha256 = models.CharField(max_length=64, validators=[sha256_validator])
    mutation_sha256 = models.CharField(max_length=64, validators=[sha256_validator])
    payload_snapshot = models.JSONField(default=dict)
    base_updated_at = models.DateTimeField(null=True, blank=True)
    occurred_at_client = models.DateTimeField()
    status = models.CharField(max_length=12, choices=Status.choices)
    result = models.JSONField(default=dict)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["package", "sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["package", "sequence"],
                name="unique_offline_package_mutation_sequence",
            )
        ]

    def __str__(self) -> str:
        return f"{self.package_id} sequence {self.sequence}: {self.status}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("Offline mutation receipts are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Offline mutation receipts are append-only.")


class OfflineConflictResolution(models.Model):
    class Decision(models.TextChoices):
        DISCARD = "discard", "Discard local change"
        REQUEUE = "requeue", "Refresh and create a replacement change"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    receipt = models.OneToOneField(
        OfflineMutationReceipt,
        related_name="resolution",
        on_delete=models.PROTECT,
    )
    decision = models.CharField(max_length=12, choices=Decision.choices)
    explanation = models.CharField(max_length=500)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="offline_conflict_resolutions",
        on_delete=models.PROTECT,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.receipt_id}: {self.decision}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("Offline conflict resolutions are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Offline conflict resolutions are append-only.")
