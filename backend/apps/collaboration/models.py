import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

from apps.accounts.models import Role
from apps.incidents.models import Incident
from apps.plans.models import PlanRevision

sha256_validator = RegexValidator(
    r"^[0-9a-f]{64}$",
    "Enter a lowercase SHA-256 digest.",
)

RESTRICTED_ASSIGNMENT_FIELDS = (
    "contact_name",
    "site_address",
    "phone_numbers",
    "contact_24_hour",
)
COLLABORATION_SECTIONS = (
    "ics205",
    "ics205.metadata",
    "ics205.assignments",
    "ics205.relationships",
)


class SensitiveFieldRule(models.Model):
    class Visibility(models.TextChoices):
        OMITTED = "omitted", "Omitted"
        RESTRICTED = "restricted", "Access restricted"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.ForeignKey(
        Incident,
        related_name="sensitive_field_rules",
        on_delete=models.PROTECT,
    )
    resource_type = models.CharField(max_length=40, default="plan_assignment")
    field_name = models.CharField(max_length=80)
    unauthorized_visibility = models.CharField(
        max_length=12,
        choices=Visibility.choices,
        default=Visibility.OMITTED,
    )
    view_roles = models.JSONField(default=list)
    edit_roles = models.JSONField(default=list)
    log_reads = models.BooleanField(default=False)
    version = models.PositiveBigIntegerField(default=1)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="created_sensitive_field_rules",
        on_delete=models.PROTECT,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="updated_sensitive_field_rules",
        on_delete=models.PROTECT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["incident", "resource_type", "field_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["incident", "resource_type", "field_name"],
                name="unique_incident_sensitive_field_rule",
            )
        ]

    def __str__(self) -> str:
        return f"{self.incident_id}:{self.field_name} v{self.version}"

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.pk:
            current = SensitiveFieldRule.objects.filter(pk=self.pk).values("version").first()
            if current:
                self.version = current["version"] + 1
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Sensitive-field rules are retained; supersede the rule.")

    def clean(self):
        if self.resource_type != "plan_assignment":
            raise ValidationError(
                {"resource_type": "Only plan_assignment is supported in this release."}
            )
        if self.field_name not in RESTRICTED_ASSIGNMENT_FIELDS:
            raise ValidationError(
                {"field_name": "Select a documented restricted assignment field."}
            )
        valid_roles = set(Role.values)
        for name, roles in (("view_roles", self.view_roles), ("edit_roles", self.edit_roles)):
            if not isinstance(roles, list) or len(roles) != len(set(roles)):
                raise ValidationError({name: "Provide a unique JSON array of roles."})
            if any(role not in valid_roles for role in roles):
                raise ValidationError({name: "A role is not recognized."})
        if not set(self.edit_roles).issubset(set(self.view_roles)):
            raise ValidationError(
                {"edit_roles": "A role cannot edit a field it is not allowed to view."}
            )


class CollaborationChange(models.Model):
    class Operation(models.TextChoices):
        REVISION_UPDATE = "revision.update", "Update revision"
        ASSIGNMENT_CREATE = "assignment.create", "Create assignment"
        ASSIGNMENT_UPDATE = "assignment.update", "Update assignment"
        ASSIGNMENT_DELETE = "assignment.delete", "Delete assignment"
        ASSIGNMENT_REORDER = "assignment.reorder", "Reorder assignments"

    class Disposition(models.TextChoices):
        SAVED = "saved", "Saved"
        CONFLICT = "conflict", "Conflict"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client_mutation_id = models.UUIDField(unique=True)
    incident = models.ForeignKey(
        Incident,
        related_name="collaboration_changes",
        on_delete=models.PROTECT,
    )
    revision = models.ForeignKey(
        PlanRevision,
        related_name="collaboration_changes",
        on_delete=models.PROTECT,
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="collaboration_changes",
        on_delete=models.PROTECT,
    )
    device_id = models.UUIDField()
    operation = models.CharField(max_length=40, choices=Operation.choices)
    object_id = models.UUIDField(null=True, blank=True)
    section = models.CharField(max_length=80, default="ics205")
    base_version = models.PositiveBigIntegerField()
    resulting_version = models.PositiveBigIntegerField(null=True, blank=True)
    affected_fields = models.JSONField(default=list)
    proposed_snapshot = models.JSONField(default=dict)
    current_snapshot = models.JSONField(default=dict)
    payload_sha256 = models.CharField(max_length=64, validators=[sha256_validator])
    disposition = models.CharField(max_length=12, choices=Disposition.choices)
    result = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["incident", "revision", "created_at"]),
            models.Index(fields=["actor", "disposition", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.operation}:{self.disposition}:{self.id}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("Collaboration changes are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Collaboration changes are append-only.")


class CollaborationResolution(models.Model):
    class Decision(models.TextChoices):
        DISCARD = "discard", "Keep saved record"
        REAPPLY = "reapply", "Copy values into a new change"
        REPLACE = "replace", "Intentionally replace current values"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conflict = models.OneToOneField(
        CollaborationChange,
        related_name="resolution",
        on_delete=models.PROTECT,
    )
    decision = models.CharField(max_length=12, choices=Decision.choices)
    explanation = models.CharField(max_length=500)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="collaboration_resolutions",
        on_delete=models.PROTECT,
    )
    replacement_change = models.OneToOneField(
        CollaborationChange,
        null=True,
        blank=True,
        related_name="replacement_resolution",
        on_delete=models.PROTECT,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.conflict_id}:{self.decision}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("Collaboration resolutions are append-only.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Collaboration resolutions are append-only.")

    def clean(self):
        if (
            self.conflict_id
            and self.conflict.disposition != CollaborationChange.Disposition.CONFLICT
        ):
            raise ValidationError({"conflict": "Only a conflict can receive a resolution."})
        if self.decision in {self.Decision.REAPPLY, self.Decision.REPLACE}:
            if not self.replacement_change_id:
                raise ValidationError(
                    {"replacement_change": "This decision must identify the saved replacement."}
                )
        elif self.replacement_change_id:
            raise ValidationError(
                {"replacement_change": "Discarding a conflict cannot have a replacement change."}
            )


class PresenceLease(models.Model):
    class Mode(models.TextChoices):
        VIEWING = "viewing", "Viewing"
        EDITING = "editing", "Editing"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.ForeignKey(
        Incident,
        related_name="presence_leases",
        on_delete=models.CASCADE,
    )
    revision = models.ForeignKey(
        PlanRevision,
        related_name="presence_leases",
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="presence_leases",
        on_delete=models.CASCADE,
    )
    device_id = models.UUIDField()
    section = models.CharField(max_length=80, default="ics205")
    object_id = models.UUIDField(null=True, blank=True)
    field_name = models.CharField(max_length=80, blank=True)
    mode = models.CharField(max_length=12, choices=Mode.choices)
    sequence = models.PositiveBigIntegerField(default=1)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["revision", "section", "user__username"]
        constraints = [
            models.UniqueConstraint(
                fields=["revision", "user", "device_id", "section"],
                name="unique_collaboration_presence_lease",
            )
        ]
        indexes = [models.Index(fields=["incident", "revision", "expires_at"])]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.revision_id}:{self.section}"
