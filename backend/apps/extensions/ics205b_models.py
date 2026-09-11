import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.incidents.models import Incident, OperationalPeriod


class ICS205BForm(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.ForeignKey(
        Incident,
        related_name="ics205b_forms",
        on_delete=models.PROTECT,
    )
    operational_period = models.ForeignKey(
        OperationalPeriod,
        related_name="ics205b_forms",
        on_delete=models.PROTECT,
    )
    prepared_at = models.DateTimeField(null=True, blank=True)
    prepared_by_name = models.CharField(max_length=160, blank=True)
    prepared_by_position = models.CharField(max_length=160, blank=True)
    prepared_by_phone = models.CharField(max_length=80, blank=True)
    prepared_by_signature = models.CharField(max_length=200, blank=True)
    incident_location = models.CharField(max_length=240, blank=True)
    state = models.CharField(max_length=80, blank=True)
    county = models.CharField(max_length=120, blank=True)
    city = models.CharField(max_length=120, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="created_ics205b_forms",
        on_delete=models.PROTECT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["incident", "operational_period__starts_at", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["incident", "operational_period"],
                name="unique_ics205b_incident_period",
            )
        ]

    def clean(self):
        super().clean()
        if (
            self.incident_id
            and self.operational_period_id
            and self.operational_period.incident_id != self.incident_id
        ):
            raise ValidationError(
                {"operational_period": "Operational period must belong to the selected incident."}
            )

    def __str__(self):
        return f"ICS 205B: {self.incident} / {self.operational_period}"


class ICS205BAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    form = models.ForeignKey(
        ICS205BForm,
        related_name="assignments",
        on_delete=models.CASCADE,
    )
    position = models.PositiveIntegerField()
    assignment = models.CharField(max_length=200, blank=True)
    it_resource_type = models.CharField(max_length=200, blank=True)
    resource_name = models.CharField(max_length=240, blank=True)
    usage_description = models.TextField(blank=True)
    platform = models.CharField(max_length=200, blank=True)
    developer = models.CharField(max_length=200, blank=True)
    login_install = models.TextField(blank=True)
    equipment_location = models.TextField(blank=True)
    poc_information = models.TextField(blank=True)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["form", "position"],
                name="unique_ics205b_form_position",
            )
        ]

    def __str__(self):
        label = self.resource_name or self.assignment or "IT resource"
        return f"{self.position}. {label}"
