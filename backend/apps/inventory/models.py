import uuid

from django.conf import settings
from django.db import models

from apps.incidents.models import Incident


class Asset(models.Model):
    class Category(models.TextChoices):
        RADIO = "radio", "Radio"
        BATTERY = "battery", "Battery"
        ANTENNA = "antenna", "Antenna"
        CABLE = "cable", "Programming cable"
        MICROPHONE = "microphone", "Microphone"
        ACCESSORY = "accessory", "Other accessory"

    class Status(models.TextChoices):
        IN_SERVICE = "in_service", "In service"
        SPARE = "spare", "Spare"
        CHECKED_OUT = "checked_out", "Checked out"
        MAINTENANCE = "maintenance", "Maintenance"
        RETIRED = "retired", "Retired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset_id = models.CharField(max_length=80, unique=True)
    category = models.CharField(max_length=20, choices=Category.choices)
    parent = models.ForeignKey(
        "self", related_name="children", null=True, blank=True, on_delete=models.PROTECT
    )
    manufacturer = models.CharField(max_length=120, blank=True)
    model = models.CharField(max_length=120, blank=True)
    serial_number = models.CharField(max_length=160, blank=True)
    alias = models.CharField(max_length=120, blank=True)
    asset_subtype = models.CharField(max_length=80, blank=True)
    flash_code = models.CharField(max_length=160, blank=True)
    subscriber_id = models.CharField(max_length=80, blank=True)
    system_ids = models.CharField(max_length=300, blank=True)
    acquisition_date = models.DateField(null=True, blank=True)
    last_calibrated_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_SERVICE)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="inventory_assets_created", on_delete=models.PROTECT
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["asset_id"]

    def __str__(self):
        return self.asset_id


class AssetCheckout(models.Model):
    class State(models.TextChoices):
        ACTIVE = "active", "Active"
        RETURNED = "returned", "Returned"
        HOLD = "hold", "Accountability hold"

    class ReturnCondition(models.TextChoices):
        NORMAL = "normal", "Returned without damage"
        DAMAGED = "damaged", "Damaged"
        LOST = "lost", "Lost or not returned"
        DISPUTED = "disputed", "Disputed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.ForeignKey(Incident, related_name="asset_checkouts", on_delete=models.PROTECT)
    asset = models.ForeignKey(Asset, related_name="checkouts", on_delete=models.PROTECT)
    assigned_name = models.CharField(max_length=200)
    assigned_organization = models.CharField(max_length=200)
    point_of_contact = models.CharField(max_length=200, blank=True)
    phone_number = models.CharField(max_length=40, blank=True)
    mailing_address = models.TextField(blank=True)
    assignment_notes = models.TextField(blank=True)
    driver_license_jurisdiction = models.CharField(max_length=8)
    driver_license_ciphertext = models.TextField()
    driver_license_last_four = models.CharField(max_length=4)
    state = models.CharField(max_length=16, choices=State.choices, default=State.ACTIVE)
    checked_out_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="asset_checkouts_created", on_delete=models.PROTECT
    )
    checked_out_at = models.DateTimeField(auto_now_add=True)
    returned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="asset_returns_recorded",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )
    returned_at = models.DateTimeField(null=True, blank=True)
    return_condition = models.CharField(max_length=16, choices=ReturnCondition.choices, blank=True)
    hold_reason = models.TextField(blank=True)
    hold_resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="asset_holds_resolved",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )
    hold_resolved_at = models.DateTimeField(null=True, blank=True)
    hold_resolution_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-checked_out_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["asset"],
                condition=models.Q(state__in=["active", "hold"]),
                name="one_open_checkout_per_asset",
            )
        ]

    def __str__(self):
        return f"{self.asset.asset_id} to {self.assigned_name}"

    @property
    def driver_license_context(self):
        return f"inventory-checkout:{self.id}"


class ProgrammingRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(Asset, related_name="programming_records", on_delete=models.PROTECT)
    template_name = models.CharField(max_length=200)
    template_version = models.CharField(max_length=80, blank=True)
    programmed_at = models.DateTimeField()
    codeplug_backup_saved = models.BooleanField()
    backup_note = models.CharField(max_length=300, blank=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="programming_records", on_delete=models.PROTECT
    )
    confirmed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-programmed_at"]

    def __str__(self):
        return f"{self.asset.asset_id}: {self.template_name}"


class MaintenanceRecord(models.Model):
    class Kind(models.TextChoices):
        INSPECTION = "inspection", "Inspection"
        CALIBRATION = "calibration", "Calibration"
        REPAIR = "repair", "Repair"
        PREVENTIVE = "preventive", "Preventive maintenance"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(Asset, related_name="maintenance_records", on_delete=models.PROTECT)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    performed_at = models.DateTimeField()
    technician = models.CharField(max_length=200)
    notes = models.TextField()
    return_to_service = models.BooleanField(default=False)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="maintenance_records", on_delete=models.PROTECT
    )
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-performed_at"]

    def __str__(self):
        return f"{self.asset.asset_id}: {self.get_kind_display()}"


class ChargingRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(Asset, related_name="charging_records", on_delete=models.PROTECT)
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.CharField(max_length=500, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="charging_records", on_delete=models.PROTECT
    )
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.asset.asset_id}: {self.started_at}"
