import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.incidents.models import Incident
from apps.plans.models import Assignment

from .fields import PortablePointField


class RadioSite(models.Model):
    class CoordinateFormat(models.TextChoices):
        MAP = "map", "Map placement"
        DECIMAL = "decimal", "Decimal degrees"
        DDM = "ddm", "Degrees decimal minutes"
        DMS = "dms", "Degrees minutes seconds"
        MGRS = "mgrs", "USNG/MGRS"
        ADDRESS = "address", "Address provider"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.ForeignKey(Incident, related_name="radio_sites", on_delete=models.PROTECT)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    location = PortablePointField(srid=4326, geography=False, spatial_index=True, editable=False)
    entered_coordinate = models.CharField(max_length=240, blank=True)
    coordinate_format = models.CharField(
        max_length=16, choices=CoordinateFormat.choices, default=CoordinateFormat.DECIMAL
    )
    address = models.TextField(blank=True)
    source_identity = models.CharField(max_length=240, blank=True)
    source_retrieved_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["incident", "name"], name="unique_radio_site_name_per_incident"
            ),
            models.CheckConstraint(
                condition=models.Q(latitude__gte=-90) & models.Q(latitude__lte=90),
                name="radio_site_valid_latitude",
            ),
            models.CheckConstraint(
                condition=models.Q(longitude__gte=-180) & models.Q(longitude__lte=180),
                name="radio_site_valid_longitude",
            ),
        ]
        indexes = [models.Index(fields=["incident", "latitude", "longitude"])]

    def __str__(self):
        return f"{self.incident}: {self.name}"

    def save(self, *args, **kwargs):
        self.full_clean(exclude=["location"])
        coordinates = [float(self.longitude), float(self.latitude)]
        if settings.ENABLE_GIS:
            from django.contrib.gis.geos import Point

            self.location = Point(*coordinates, srid=4326)
        else:
            self.location = {"type": "Point", "coordinates": coordinates}
        return super().save(*args, **kwargs)

    def clean(self):
        if not Decimal("-90") <= self.latitude <= Decimal("90"):
            raise ValidationError({"latitude": "Latitude must be between -90 and 90."})
        if not Decimal("-180") <= self.longitude <= Decimal("180"):
            raise ValidationError({"longitude": "Longitude must be between -180 and 180."})


class ManualRing(models.Model):
    class Type(models.TextChoices):
        OPERATIONAL = "operational", "Operational"
        FRINGE = "fringe", "Fringe / uncertain"
        COORDINATION = "coordination", "Coordination"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(RadioSite, related_name="rings", on_delete=models.PROTECT)
    ring_type = models.CharField(max_length=16, choices=Type.choices)
    radius_m = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(2_147_483_647)]
    )
    label = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["site", "ring_type", "radius_m"]
        constraints = [
            models.UniqueConstraint(
                fields=["site", "ring_type", "radius_m"], name="unique_manual_ring"
            )
        ]

    def __str__(self):
        return f"{self.site}: {self.get_ring_type_display()} {self.radius_m} m"

    @property
    def incident(self):
        return self.site.incident


class SiteAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(RadioSite, related_name="assignment_links", on_delete=models.PROTECT)
    assignment = models.ForeignKey(Assignment, related_name="site_links", on_delete=models.PROTECT)
    site_snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["assignment__position", "site__name"]
        constraints = [
            models.UniqueConstraint(fields=["site", "assignment"], name="unique_site_assignment")
        ]

    def __str__(self):
        return f"{self.site} ↔ {self.assignment}"

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.assignment.revision.is_locked:
            raise ValidationError("Approved assignment site links are immutable.")
        return super().delete(*args, **kwargs)

    def clean(self):
        if self.site_id and self.assignment_id:
            if self.site.incident_id != self.assignment.revision.plan.incident_id:
                raise ValidationError("Site and assignment must belong to the same incident.")
            if self.assignment.revision.is_locked and not self.site_snapshot:
                raise ValidationError("Approved assignment site links are immutable.")

    @property
    def incident(self):
        return self.site.incident

    @property
    def revision(self):
        return self.assignment.revision
