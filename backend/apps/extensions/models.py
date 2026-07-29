import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.incidents.models import Incident
from apps.plans.models import PlanRevision


class ExtensionInstallation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    extension_key = models.SlugField(max_length=120, unique=True)
    extension_version = models.CharField(max_length=40)
    contract_version = models.CharField(max_length=20)
    manifest_snapshot = models.JSONField()
    manifest_sha256 = models.CharField(max_length=64)
    enabled = models.BooleanField(default=False)
    installed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="installed_extensions",
        on_delete=models.PROTECT,
    )
    installed_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="updated_extensions",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["extension_key"]

    def __str__(self):
        state = "enabled" if self.enabled else "disabled"
        return f"{self.extension_key} {self.extension_version} ({state})"

    def delete(self, *args, **kwargs):
        raise ValidationError("Extension installation history is retained.")


class ExtensionExecution(models.Model):
    class CapabilityKind(models.TextChoices):
        TOOL = "tool", "Tool"
        REPORT = "report", "Report"

    class Status(models.TextChoices):
        COMPLETE = "complete", "Complete"
        FAILED = "failed", "Failed"

    class OutputClassification(models.TextChoices):
        DRAFT = "draft", "Draft"
        DECISION_SUPPORT = "decision_support", "Decision support"
        OFFICIAL = "official", "Official"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    installation = models.ForeignKey(
        ExtensionInstallation,
        related_name="executions",
        on_delete=models.PROTECT,
    )
    extension_key = models.SlugField(max_length=120)
    extension_version = models.CharField(max_length=40)
    contract_version = models.CharField(max_length=20)
    capability = models.SlugField(max_length=120)
    capability_kind = models.CharField(max_length=12, choices=CapabilityKind.choices)
    incident = models.ForeignKey(
        Incident,
        related_name="extension_executions",
        on_delete=models.PROTECT,
    )
    source_revision = models.ForeignKey(
        PlanRevision,
        related_name="extension_executions",
        on_delete=models.PROTECT,
    )
    input_snapshot = models.JSONField()
    input_sha256 = models.CharField(max_length=64)
    result_snapshot = models.JSONField(default=dict)
    result_sha256 = models.CharField(max_length=64)
    output_classification = models.CharField(
        max_length=24,
        choices=OutputClassification.choices,
    )
    status = models.CharField(max_length=12, choices=Status.choices)
    failure_code = models.CharField(max_length=80, blank=True)
    failure_message = models.CharField(max_length=240, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="extension_executions",
        on_delete=models.PROTECT,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["incident", "extension_key", "created_at"],
                name="extension_inc_key_idx",
            )
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status="complete",
                        failure_code="",
                        failure_message="",
                    )
                    | models.Q(status="failed")
                ),
                name="extension_execution_failure_consistent",
            )
        ]

    def __str__(self):
        return f"{self.extension_key}:{self.capability} ({self.status})"

    def save(self, *args, **kwargs):
        if self.pk and ExtensionExecution.objects.filter(pk=self.pk).exists():
            raise ValidationError("Extension executions are immutable after creation.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Extension executions are retained.")
