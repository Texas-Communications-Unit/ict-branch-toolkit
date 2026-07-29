import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.incidents.models import Incident
from apps.plans.models import PlanRevision


class DeconflictionAnalysis(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        APPROVED = "approved", "Approved"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.ForeignKey(
        Incident,
        related_name="deconfliction_analyses",
        on_delete=models.PROTECT,
    )
    approved_revision = models.ForeignKey(
        PlanRevision,
        related_name="deconfliction_analyses",
        on_delete=models.PROTECT,
    )
    rule_set_id = models.CharField(max_length=80)
    rule_set_version = models.CharField(max_length=120)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    input_snapshot = models.JSONField()
    input_sha256 = models.CharField(max_length=64)
    result_snapshot = models.JSONField()
    result_sha256 = models.CharField(max_length=64)
    warning_count = models.PositiveIntegerField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="created_deconfliction_analyses",
        on_delete=models.PROTECT,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="approved_deconfliction_analyses",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status="draft",
                        approved_by__isnull=True,
                        approved_at__isnull=True,
                    )
                    | models.Q(
                        status="approved",
                        approved_by__isnull=False,
                        approved_at__isnull=False,
                    )
                ),
                name="deconfliction_approval_consistent",
            )
        ]
        indexes = [
            models.Index(
                fields=["incident", "approved_revision", "created_at"],
                name="deconf_inc_revision_idx",
            )
        ]

    def __str__(self):
        return f"{self.incident}: {self.rule_set_version} ({self.warning_count} warnings)"

    def save(self, *args, **kwargs):
        if self.pk and DeconflictionAnalysis.objects.filter(pk=self.pk).exists():
            raise ValidationError("Deconfliction analyses are immutable after creation.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Deconfliction analyses are retained.")

    @property
    def is_locked(self):
        return self.status == self.Status.APPROVED


class DeconflictionFindingDisposition(models.Model):
    class Disposition(models.TextChoices):
        REVIEWED_NO_CHANGE = "reviewed_no_change", "Reviewed — no plan change"
        PLAN_CHANGE_REQUIRED = "plan_change_required", "Plan change required"
        SPECIAL_ACCOMMODATION_REQUIRED = (
            "special_accommodation_required",
            "Special accommodation required",
        )
        SOURCE_REVIEW_REQUIRED = "source_review_required", "Source review required"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    analysis = models.ForeignKey(
        DeconflictionAnalysis,
        related_name="finding_dispositions",
        on_delete=models.PROTECT,
    )
    finding_key = models.CharField(max_length=64)
    rule_id = models.CharField(max_length=16)
    disposition = models.CharField(max_length=40, choices=Disposition.choices)
    explanation = models.CharField(max_length=1000)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="deconfliction_finding_dispositions",
        on_delete=models.PROTECT,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(
                fields=["analysis", "finding_key", "created_at"],
                name="deconf_finding_review_idx",
            )
        ]

    def __str__(self):
        return f"{self.rule_id}:{self.finding_key}:{self.disposition}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Finding dispositions are append-only.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Finding dispositions are retained.")

    def clean(self):
        if not self.analysis_id:
            return
        warning = next(
            (
                item
                for item in self.analysis.result_snapshot.get("warnings", [])
                if item.get("finding_key") == self.finding_key
            ),
            None,
        )
        if warning is None:
            raise ValidationError(
                {"finding_key": "The finding does not belong to this retained analysis."}
            )
        if warning.get("rule_id") != self.rule_id:
            raise ValidationError({"rule_id": "The rule ID does not match the retained finding."})
