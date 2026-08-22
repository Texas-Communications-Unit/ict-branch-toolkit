import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models

sha256_validator = RegexValidator(r"^[0-9a-f]{64}$", "Enter a lowercase SHA-256 digest.")


class FccImportBatch(models.Model):
    class Dataset(models.TextChoices):
        ASR = "asr", "Antenna Structure Registration"
        ULS_PRIVATE = "uls_private", "ULS private land mobile"
        ULS_COMMERCIAL = "uls_commercial", "ULS commercial land mobile"

    class ArchiveKind(models.TextChoices):
        COMPLETE = "complete", "Complete reconciliation"
        DAILY = "daily", "Daily transaction"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dataset = models.CharField(max_length=24, choices=Dataset.choices)
    archive_kind = models.CharField(
        max_length=12, choices=ArchiveKind.choices, default=ArchiveKind.COMPLETE
    )
    archive_name = models.CharField(max_length=80)
    source_url = models.URLField(max_length=500)
    content_sha256 = models.CharField(max_length=64, validators=[sha256_validator])
    parser_version = models.CharField(max_length=40)
    retrieved_at = models.DateTimeField()
    record_counts = models.JSONField(default=dict)
    is_current = models.BooleanField(default=True)
    imported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-imported_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["dataset", "content_sha256"], name="unique_fcc_dataset_archive_digest"
            )
        ]
        indexes = [models.Index(fields=["dataset", "is_current"])]

    def __str__(self) -> str:
        return f"{self.get_dataset_display()} {self.archive_name}"


class AntennaStructure(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(
        FccImportBatch, related_name="antenna_structures", on_delete=models.PROTECT
    )
    registration_number = models.CharField(max_length=20)
    unique_system_identifier = models.CharField(max_length=24, blank=True)
    status_code = models.CharField(max_length=8, blank=True)
    owner_name = models.CharField(max_length=300, blank=True)
    owner_frn = models.CharField(max_length=20, blank=True)
    structure_type = models.CharField(max_length=40, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=7, null=True, blank=True)
    structure_height_m = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    ground_elevation_m = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    overall_height_m = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    overall_height_amsl_m = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True
    )
    faa_study_number = models.CharField(max_length=80, blank=True)
    painting_lighting = models.CharField(max_length=120, blank=True)
    construction_date = models.DateField(null=True, blank=True)
    dismantlement_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["registration_number"]
        indexes = [models.Index(fields=["batch", "latitude", "longitude"])]
        constraints = [
            models.UniqueConstraint(
                fields=["batch", "registration_number"], name="unique_asr_registration_batch"
            ),
            models.CheckConstraint(
                condition=models.Q(latitude__isnull=True)
                | (models.Q(latitude__gte=-90) & models.Q(latitude__lte=90)),
                name="fcc_asr_valid_latitude",
            ),
            models.CheckConstraint(
                condition=models.Q(longitude__isnull=True)
                | (models.Q(longitude__gte=-180) & models.Q(longitude__lte=180)),
                name="fcc_asr_valid_longitude",
            ),
        ]

    def __str__(self) -> str:
        return f"ASR {self.registration_number}"


class UlsLicense(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(FccImportBatch, related_name="licenses", on_delete=models.PROTECT)
    unique_system_identifier = models.CharField(max_length=24)
    call_sign = models.CharField(max_length=20)
    license_status = models.CharField(max_length=8)
    radio_service_code = models.CharField(max_length=8)
    applicant_type_code = models.CharField(max_length=8, blank=True)
    selection_rule = models.CharField(max_length=40)
    licensee_name = models.CharField(max_length=300, blank=True)
    frn = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=300, blank=True)
    city = models.CharField(max_length=120, blank=True)
    state = models.CharField(max_length=8, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    grant_date = models.DateField(null=True, blank=True)
    expiration_date = models.DateField(null=True, blank=True)
    cancellation_date = models.DateField(null=True, blank=True)
    last_action_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["call_sign", "unique_system_identifier"]
        constraints = [
            models.UniqueConstraint(
                fields=["batch", "unique_system_identifier"], name="unique_uls_license_batch"
            )
        ]
        indexes = [
            models.Index(fields=["call_sign"]),
            models.Index(fields=["radio_service_code", "license_status"]),
        ]

    def __str__(self) -> str:
        return f"{self.call_sign} ({self.radio_service_code})"


class UlsLocation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    license = models.ForeignKey(UlsLicense, related_name="locations", on_delete=models.PROTECT)
    location_number = models.PositiveIntegerField()
    location_type_code = models.CharField(max_length=8, blank=True)
    location_class_code = models.CharField(max_length=8, blank=True)
    address = models.CharField(max_length=300, blank=True)
    city = models.CharField(max_length=120, blank=True)
    county = models.CharField(max_length=120, blank=True)
    state = models.CharField(max_length=8, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=7, null=True, blank=True)
    ground_elevation_m = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    asr_registration_number = models.CharField(max_length=20, blank=True)
    structure_type = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ["license", "location_number"]
        indexes = [models.Index(fields=["asr_registration_number"])]
        constraints = [
            models.UniqueConstraint(
                fields=["license", "location_number"], name="unique_uls_location_license"
            ),
            models.CheckConstraint(
                condition=models.Q(latitude__isnull=True)
                | (models.Q(latitude__gte=-90) & models.Q(latitude__lte=90)),
                name="fcc_uls_location_valid_latitude",
            ),
            models.CheckConstraint(
                condition=models.Q(longitude__isnull=True)
                | (models.Q(longitude__gte=-180) & models.Q(longitude__lte=180)),
                name="fcc_uls_location_valid_longitude",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.license.call_sign} location {self.location_number}"


class UlsFrequency(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    license = models.ForeignKey(UlsLicense, related_name="frequencies", on_delete=models.PROTECT)
    location_number = models.PositiveIntegerField()
    antenna_number = models.PositiveIntegerField()
    station_class_code = models.CharField(max_length=12, blank=True)
    frequency_hz = models.BigIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10_000_000_000)]
    )
    output_power_w = models.DecimalField(max_digits=15, decimal_places=3, null=True, blank=True)
    effective_radiated_power_w = models.DecimalField(
        max_digits=15, decimal_places=3, null=True, blank=True
    )
    number_of_units = models.PositiveIntegerField(null=True, blank=True)
    source_frequency_id = models.CharField(max_length=24, blank=True)

    class Meta:
        ordering = ["license", "location_number", "antenna_number", "frequency_hz"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "license",
                    "location_number",
                    "antenna_number",
                    "frequency_hz",
                    "station_class_code",
                    "source_frequency_id",
                ],
                name="unique_uls_frequency_license_location",
            )
        ]

    def __str__(self) -> str:
        return f"{self.license.call_sign} {self.frequency_hz} Hz"


class UlsEmission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    license = models.ForeignKey(UlsLicense, related_name="emissions", on_delete=models.PROTECT)
    location_number = models.PositiveIntegerField()
    antenna_number = models.PositiveIntegerField()
    frequency_hz = models.BigIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10_000_000_000)]
    )
    emission_designator = models.CharField(max_length=40)
    source_frequency_id = models.CharField(max_length=24, blank=True)

    class Meta:
        ordering = ["license", "location_number", "antenna_number", "frequency_hz"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "license",
                    "location_number",
                    "antenna_number",
                    "frequency_hz",
                    "emission_designator",
                    "source_frequency_id",
                ],
                name="unique_uls_emission_license_frequency",
            )
        ]

    def __str__(self) -> str:
        return f"{self.license.call_sign} {self.emission_designator}"
