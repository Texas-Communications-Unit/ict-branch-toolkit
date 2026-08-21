import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.db import models

from apps.incidents.models import Incident, OperationalPeriod
from apps.resources.models import ConventionalChannel, TrunkedTalkgroup


class ICS205Plan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.ForeignKey(Incident, related_name="ics205_plans", on_delete=models.PROTECT)
    operational_period = models.ForeignKey(
        OperationalPeriod, related_name="ics205_plans", on_delete=models.PROTECT
    )
    title = models.CharField(max_length=200, default="Incident Radio Communications Plan")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["incident", "operational_period"], name="unique_ics205_incident_period"
            )
        ]

    def __str__(self):
        return f"{self.incident}: {self.operational_period}"

    def clean(self):
        if self.operational_period_id and self.incident_id:
            if self.operational_period.incident_id != self.incident_id:
                raise ValidationError("Operational period must belong to the plan incident.")


class PlanRevision(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        APPROVED = "approved", "Approved"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan = models.ForeignKey(ICS205Plan, related_name="revisions", on_delete=models.PROTECT)
    number = models.PositiveIntegerField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    prepared_by_name = models.CharField(max_length=160, blank=True)
    prepared_by_position = models.CharField(max_length=160, blank=True)
    prepared_at = models.DateTimeField(null=True, blank=True)
    copied_from = models.ForeignKey(
        "self", null=True, blank=True, related_name="copies", on_delete=models.PROTECT
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="created_plan_revisions", on_delete=models.PROTECT
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="approved_plan_revisions",
        on_delete=models.PROTECT,
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    collaboration_version = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["plan", "-number"]
        constraints = [
            models.UniqueConstraint(fields=["plan", "number"], name="unique_plan_revision_number")
        ]

    def __str__(self):
        return f"{self.plan} revision {self.number}"

    def save(self, *args, **kwargs):
        if (
            self.pk
            and PlanRevision.objects.filter(
                pk=self.pk, status=PlanRevision.Status.APPROVED
            ).exists()
        ):
            raise ValidationError("Approved revisions are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Plan revisions are retained.")

    @property
    def is_locked(self):
        return self.status == self.Status.APPROVED


class Assignment(models.Model):
    PUBLISHABLE_CONTACT_FIELDS = (
        "contact_name",
        "site_address",
        "phone_numbers",
        "contact_24_hour",
    )

    class ContactPublicationPlacement(models.TextChoices):
        REMARKS = "remarks", "Assignment remarks"
        SPECIAL_INSTRUCTIONS = "special_instructions", "Plan-wide special instructions"

    class OperatingClassification(models.TextChoices):
        FIXED_PAIR = "fixed_pair", "Fixed-frequency pair"
        TRANSMIT_ONLY = "transmit_only", "Broadcast/transmit-only"
        RECEIVE_ONLY = "receive_only", "Receive-only"
        NAMED_SYSTEM = (
            "named_system",
            "Named system channel — frequencies intentionally omitted",
        )
        DYNAMIC_POOL = "dynamic_pool", "Dynamic/multi-channel pool"
        NOT_DETERMINED = "not_determined", "Not yet determined"

    class TechnologySubtype(models.TextChoices):
        TRUNKED_TALKGROUP = "trunked_talkgroup", "Trunked talkgroup"
        LTE_5G = "lte_5g", "LTE/5G"
        SCADA = "scada", "SCADA"
        SPREAD_SPECTRUM = "spread_spectrum", "Spread-spectrum"
        OTHER = "other", "Other system"

    class NoteType(models.TextChoices):
        NONE = "", "None"
        REMOTE_BASE = "remote_base", "Remote Base"
        LINK = "link", "Link"
        PATCH = "patch", "Patch"
        OTHER = "other", "Other"

    class ChannelWidth(models.IntegerChoices):
        KHZ_6_25 = 6_250, "6.25 kHz"
        KHZ_12_5 = 12_500, "12.5 kHz"
        KHZ_25 = 25_000, "25 kHz legacy wideband"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    revision = models.ForeignKey(PlanRevision, related_name="assignments", on_delete=models.PROTECT)
    position = models.PositiveIntegerField(validators=[MaxValueValidator(2_147_483_647)])
    function = models.CharField(max_length=160)
    channel_name = models.CharField(max_length=160)
    assignment = models.CharField(max_length=200, blank=True)
    conventional_channel = models.ForeignKey(
        ConventionalChannel, null=True, blank=True, on_delete=models.PROTECT
    )
    trunked_talkgroup = models.ForeignKey(
        TrunkedTalkgroup, null=True, blank=True, on_delete=models.PROTECT
    )
    subscriber_profile_version = models.ForeignKey(
        "rf_analysis.SubscriberProfileVersion",
        null=True,
        blank=True,
        related_name="plan_assignments",
        on_delete=models.PROTECT,
    )
    resource_snapshot = models.JSONField(default=dict)
    operating_classification = models.CharField(
        max_length=24,
        choices=OperatingClassification.choices,
        default=OperatingClassification.NOT_DETERMINED,
    )
    technology_subtype = models.CharField(
        max_length=24,
        choices=TechnologySubtype.choices,
        blank=True,
    )
    rx_frequency_hz = models.BigIntegerField(null=True, blank=True)
    rx_channel_width_hz = models.PositiveIntegerField(
        choices=ChannelWidth.choices,
        null=True,
        blank=True,
        validators=[MaxValueValidator(2_147_483_647)],
    )
    tx_channel_width_hz = models.PositiveIntegerField(
        choices=ChannelWidth.choices,
        null=True,
        blank=True,
        validators=[MaxValueValidator(2_147_483_647)],
    )
    rx_squelch = models.CharField(max_length=40, blank=True)
    tx_frequency_hz = models.BigIntegerField(null=True, blank=True)
    tx_squelch = models.CharField(max_length=40, blank=True)
    mode = models.CharField(max_length=40, blank=True)
    remarks = models.TextField(blank=True)
    structured_note = models.CharField(max_length=20, choices=NoteType.choices, blank=True)
    contact_name = models.CharField(max_length=160, blank=True)
    site_address = models.TextField(blank=True)
    phone_numbers = models.CharField(max_length=240, blank=True)
    contact_24_hour = models.CharField(max_length=240, blank=True)
    published_contact_fields = models.JSONField(default=list, blank=True)
    contact_publication_purpose = models.CharField(max_length=240, blank=True)
    contact_publication_placement = models.CharField(
        max_length=24,
        choices=ContactPublicationPlacement.choices,
        default=ContactPublicationPlacement.REMARKS,
    )
    collaboration_version = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["revision", "position"], name="unique_assignment_revision_position"
            ),
            models.CheckConstraint(
                condition=~(
                    models.Q(conventional_channel__isnull=False)
                    & models.Q(trunked_talkgroup__isnull=False)
                ),
                name="assignment_single_resource_type",
            ),
        ]

    def __str__(self):
        return f"{self.revision} row {self.position}: {self.channel_name}"

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.revision.is_locked:
            raise ValidationError("Approved revisions are immutable.")
        return super().delete(*args, **kwargs)

    def clean(self):
        if self.revision_id and self.revision.is_locked:
            raise ValidationError("Approved revisions are immutable.")
        if self.subscriber_profile_version_id:
            profile_version = self.subscriber_profile_version
            if profile_version.status != "approved":
                raise ValidationError(
                    {
                        "subscriber_profile_version": (
                            "Only an approved subscriber programming profile version "
                            "may be selected."
                        )
                    }
                )
            if (
                self.revision_id
                and profile_version.profile.incident_id != self.revision.plan.incident_id
            ):
                raise ValidationError(
                    {
                        "subscriber_profile_version": (
                            "The subscriber programming profile must belong to the plan incident."
                        )
                    }
                )

        classification = self.operating_classification
        has_rx = self.rx_frequency_hz is not None
        has_tx = self.tx_frequency_hz is not None
        errors: dict[str, str] = {}
        if classification == self.OperatingClassification.FIXED_PAIR and not (has_rx and has_tx):
            errors["operating_classification"] = (
                "Fixed-frequency pair requires both receive and transmit frequencies."
            )
        elif classification == self.OperatingClassification.TRANSMIT_ONLY and (
            has_rx or not has_tx
        ):
            errors["operating_classification"] = (
                "Broadcast/transmit-only requires a transmit frequency and a blank "
                "receive frequency."
            )
        elif classification == self.OperatingClassification.RECEIVE_ONLY and (not has_rx or has_tx):
            errors["operating_classification"] = (
                "Receive-only requires a receive frequency and a blank transmit frequency."
            )
        elif classification in {
            self.OperatingClassification.NAMED_SYSTEM,
            self.OperatingClassification.DYNAMIC_POOL,
        } and (has_rx or has_tx):
            errors["operating_classification"] = (
                "This operating classification intentionally omits fixed receive and "
                "transmit frequencies."
            )

        if classification == self.OperatingClassification.NAMED_SYSTEM:
            if not self.technology_subtype:
                errors["technology_subtype"] = "Named system channels require a technology subtype."
        elif self.technology_subtype:
            errors["technology_subtype"] = (
                "Technology subtype applies only to a named system channel."
            )

        if errors:
            raise ValidationError(errors)

        published_fields = self.published_contact_fields
        if not isinstance(published_fields, list) or len(published_fields) != len(
            set(published_fields)
        ):
            errors["published_contact_fields"] = (
                "Provide a unique list of contact fields to publish."
            )
        elif any(field not in self.PUBLISHABLE_CONTACT_FIELDS for field in published_fields):
            errors["published_contact_fields"] = "A selected contact field is not publishable."
        elif any(not getattr(self, field, "") for field in published_fields):
            errors["published_contact_fields"] = (
                "Every selected contact field must contain a value."
            )
        if published_fields and not self.contact_publication_purpose.strip():
            errors["contact_publication_purpose"] = (
                "Record an operational purpose before publishing contact information."
            )
        if errors:
            raise ValidationError(errors)


class AssignmentRelationship(models.Model):
    class Type(models.TextChoices):
        REMOTE_BASE = "remote_base", "Remote Base"
        LINK = "link", "Link"
        PATCH = "patch", "Patch"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    revision = models.ForeignKey(
        PlanRevision, related_name="relationships", on_delete=models.PROTECT
    )
    relationship_type = models.CharField(max_length=20, choices=Type.choices)
    label = models.CharField(max_length=160, blank=True)
    assignments = models.ManyToManyField(Assignment, related_name="relationships")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_relationship_type_display()}: {self.label}"

    def clean(self):
        if self.revision_id and self.revision.is_locked:
            raise ValidationError("Approved revisions are immutable.")
