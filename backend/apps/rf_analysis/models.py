import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.incidents.models import Incident
from apps.sites.models import RadioSite

FREQUENCY_MAX_HZ = 1_000_000_000_000
POWER_MAX_W = Decimal("10000000")
GAIN_MIN_DB = Decimal("-200")
GAIN_MAX_DB = Decimal("200")
LOSS_MAX_DB = Decimal("1000")
LENGTH_MAX_M = Decimal("1000000")
HEIGHT_MIN_M = Decimal("-100000")
HEIGHT_MAX_M = Decimal("100000")


class SubscriberProfile(models.Model):
    class ProfileType(models.TextChoices):
        PORTABLE = "portable", "Portable"
        MOBILE = "mobile", "Mobile"
        FIXED = "fixed", "Fixed"
        CONFIGURABLE = "configurable", "Configurable"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.ForeignKey(
        Incident,
        related_name="subscriber_profiles",
        on_delete=models.PROTECT,
    )
    name = models.CharField(max_length=160)
    profile_type = models.CharField(max_length=20, choices=ProfileType.choices)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="created_subscriber_profiles",
        on_delete=models.PROTECT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["incident", "name", "created_at"]
        indexes = [
            models.Index(fields=["incident", "archived_at"], name="rf_profile_incident_active_idx")
        ]

    def __str__(self):
        return f"{self.incident}: {self.name}"

    def delete(self, *args, **kwargs):
        raise ValidationError("Subscriber profiles are archived, not deleted.")


class SubscriberProfileVersion(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        APPROVED = "approved", "Approved"

    class ERPSource(models.TextChoices):
        UNKNOWN = "unknown", "Unknown"
        ENTERED = "entered", "Entered"
        CALCULATED = "calculated", "Calculated"

    class AntennaGainReference(models.TextChoices):
        UNKNOWN = "unknown", "Unknown"
        DBI = "dbi", "dBi"
        DBD = "dbd", "dBd"

    class Polarization(models.TextChoices):
        UNKNOWN = "unknown", "Unknown"
        VERTICAL = "vertical", "Vertical"
        HORIZONTAL = "horizontal", "Horizontal"
        CIRCULAR = "circular", "Circular"
        MIXED = "mixed", "Mixed"

    class FrequencyBand(models.TextChoices):
        UNKNOWN = "unknown", "Unknown"
        VHF_LOW = "vhf_low", "VHF low"
        VHF_HIGH = "vhf_high", "VHF high"
        UHF = "uhf", "UHF"
        BAND_700 = "700", "700 MHz"
        BAND_800 = "800", "800 MHz"
        BAND_900 = "900", "900 MHz"
        OTHER = "other", "Other"

    class MountingType(models.TextChoices):
        UNKNOWN = "unknown", "Unknown"
        HANDHELD = "handheld", "Handheld"
        VEHICLE = "vehicle", "Vehicle"
        STRUCTURE = "structure", "Structure"
        TOWER = "tower", "Tower"
        MAST = "mast", "Mast"
        OTHER = "other", "Other"

    class InputBasis(models.TextChoices):
        UNKNOWN = "unknown", "Unknown"
        RECORDED_FACT = "recorded_fact", "Recorded fact"
        MODELED_ASSUMPTION = "modeled_assumption", "Modeled assumption"
        MIXED = "mixed", "Mixed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        SubscriberProfile,
        related_name="versions",
        on_delete=models.PROTECT,
    )
    number = models.PositiveIntegerField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)

    tx_frequency_hz = models.BigIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(FREQUENCY_MAX_HZ)],
    )
    rx_frequency_hz = models.BigIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(FREQUENCY_MAX_HZ)],
    )
    transmitter_power_w = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(POWER_MAX_W)],
    )
    effective_radiated_power_w = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(POWER_MAX_W)],
    )
    erp_source = models.CharField(
        max_length=12,
        choices=ERPSource.choices,
        default=ERPSource.UNKNOWN,
    )
    receiver_sensitivity_dbm = models.DecimalField(
        max_digits=7,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("-300")), MaxValueValidator(Decimal("100"))],
    )
    antenna_model = models.CharField(max_length=200, null=True, blank=True, default=None)
    antenna_gain_db = models.DecimalField(
        max_digits=7,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(GAIN_MIN_DB), MaxValueValidator(GAIN_MAX_DB)],
    )
    antenna_gain_reference = models.CharField(
        max_length=12,
        choices=AntennaGainReference.choices,
        default=AntennaGainReference.UNKNOWN,
    )
    feed_line_type = models.CharField(max_length=160, null=True, blank=True, default=None)
    feed_line_length_m = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(LENGTH_MAX_M)],
    )
    feed_line_loss_db = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(LOSS_MAX_DB)],
    )
    additional_system_loss_db = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(LOSS_MAX_DB)],
    )
    polarization = models.CharField(
        max_length=12,
        choices=Polarization.choices,
        default=Polarization.UNKNOWN,
    )
    frequency_band = models.CharField(
        max_length=12,
        choices=FrequencyBand.choices,
        default=FrequencyBand.UNKNOWN,
    )
    emission_designator = models.CharField(max_length=32, null=True, blank=True, default=None)
    emission_bandwidth_hz = models.BigIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(FREQUENCY_MAX_HZ)],
    )
    mounting_type = models.CharField(
        max_length=16,
        choices=MountingType.choices,
        default=MountingType.UNKNOWN,
    )
    antenna_center_agl_m = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(HEIGHT_MAX_M)],
    )
    antenna_center_amsl_m = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(HEIGHT_MIN_M), MaxValueValidator(HEIGHT_MAX_M)],
    )
    haat_m = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(HEIGHT_MIN_M), MaxValueValidator(HEIGHT_MAX_M)],
    )
    input_basis = models.CharField(
        max_length=24,
        choices=InputBasis.choices,
        default=InputBasis.UNKNOWN,
    )
    notes = models.TextField(null=True, blank=True, default=None)
    erp_calculation_path = models.JSONField(default=dict, blank=True)

    input_snapshot = models.JSONField(default=dict, blank=True)
    input_sha256 = models.CharField(max_length=64, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="created_subscriber_profile_versions",
        on_delete=models.PROTECT,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="approved_subscriber_profile_versions",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["profile", "-number"]
        constraints = [
            models.UniqueConstraint(
                fields=["profile", "number"],
                name="unique_subscriber_profile_version_number",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status="draft",
                        approved_by__isnull=True,
                        approved_at__isnull=True,
                        input_sha256="",
                    )
                    | (
                        models.Q(
                            status="approved",
                            approved_by__isnull=False,
                            approved_at__isnull=False,
                        )
                        & ~models.Q(input_sha256="")
                    )
                ),
                name="rf_profile_version_approval_consistent",
            ),
        ]

    def __str__(self):
        return f"{self.profile} version {self.number}"

    def save(self, *args, **kwargs):
        if (
            self.pk
            and SubscriberProfileVersion.objects.filter(
                pk=self.pk,
                status=SubscriberProfileVersion.Status.APPROVED,
            ).exists()
        ):
            raise ValidationError("Approved subscriber profile versions are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Subscriber profile versions are retained.")

    @property
    def is_locked(self):
        return self.status == self.Status.APPROVED


class RFAnalysisInputSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.ForeignKey(
        Incident,
        related_name="rf_analysis_input_snapshots",
        on_delete=models.PROTECT,
    )
    profile_version = models.ForeignKey(
        SubscriberProfileVersion,
        related_name="analysis_input_snapshots",
        on_delete=models.PROTECT,
    )
    label = models.CharField(max_length=200)
    input_snapshot = models.JSONField()
    input_sha256 = models.CharField(max_length=64)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="created_rf_analysis_input_snapshots",
        on_delete=models.PROTECT,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="approved_rf_analysis_input_snapshots",
        on_delete=models.PROTECT,
    )
    approved_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["incident", "archived_at"],
                name="rf_snap_incident_active_idx",
            )
        ]

    def __str__(self):
        return f"{self.label}: {self.profile_version}"

    def save(self, *args, **kwargs):
        if self.pk and RFAnalysisInputSnapshot.objects.filter(pk=self.pk).exists():
            raise ValidationError("RF analysis input snapshots are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("RF analysis input snapshots are retained.")


class ElevationSnapshot(models.Model):
    class AcquisitionState(models.TextChoices):
        COMPLETE = "complete", "Complete"
        PARTIAL = "partial", "Partial"
        MISSING = "missing", "Missing"
        OUT_OF_COVERAGE = "out_of_coverage", "Out of coverage"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.ForeignKey(
        Incident,
        related_name="elevation_snapshots",
        on_delete=models.PROTECT,
    )
    site = models.ForeignKey(
        RadioSite,
        related_name="elevation_snapshots",
        on_delete=models.PROTECT,
    )
    query_sha256 = models.CharField(max_length=64, db_index=True)
    query_snapshot = models.JSONField()
    provider = models.CharField(max_length=160)
    dataset_product = models.CharField(max_length=240)
    horizontal_crs = models.CharField(max_length=120)
    vertical_crs = models.CharField(max_length=120)
    target_vertical_crs = models.CharField(max_length=120)
    resolution_m = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(LENGTH_MAX_M)],
    )
    source_version = models.CharField(max_length=160, blank=True)
    source_retrieved_at = models.DateTimeField(null=True, blank=True)
    license_terms_url = models.URLField(max_length=500, blank=True)
    permitted_use = models.TextField()
    coverage = models.JSONField(default=dict, blank=True)
    source_content_sha256 = models.CharField(max_length=64, blank=True)
    acquisition_state = models.CharField(max_length=24, choices=AcquisitionState.choices)
    sample_snapshot = models.JSONField()
    sample_sha256 = models.CharField(max_length=64)
    transformation = models.JSONField(default=dict, blank=True)
    warnings = models.JSONField(default=list, blank=True)
    retrieved_at = models.DateTimeField()
    stale_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="created_elevation_snapshots",
        on_delete=models.PROTECT,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["incident", "site", "query_sha256"],
                name="rf_elev_cache_lookup_idx",
            )
        ]

    def __str__(self):
        return f"{self.site}: {self.dataset_product} ({self.acquisition_state})"

    def save(self, *args, **kwargs):
        if self.pk and ElevationSnapshot.objects.filter(pk=self.pk).exists():
            raise ValidationError("Elevation snapshots are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Elevation snapshots are retained.")

    @property
    def current_state(self):
        if self.stale_at and self.stale_at <= timezone.now():
            return "stale"
        return self.acquisition_state


class HAATCalculation(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        APPROVED = "approved", "Approved"

    class CalculationState(models.TextChoices):
        COMPLETE = "complete", "Complete"
        PARTIAL = "partial", "Partial"
        UNAVAILABLE = "unavailable", "Unavailable"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.ForeignKey(
        Incident,
        related_name="haat_calculations",
        on_delete=models.PROTECT,
    )
    site = models.ForeignKey(
        RadioSite,
        related_name="haat_calculations",
        on_delete=models.PROTECT,
    )
    profile_version = models.ForeignKey(
        SubscriberProfileVersion,
        related_name="haat_calculations",
        on_delete=models.PROTECT,
    )
    rf_input_snapshot = models.ForeignKey(
        RFAnalysisInputSnapshot,
        related_name="haat_calculations",
        on_delete=models.PROTECT,
    )
    elevation_snapshot = models.ForeignKey(
        ElevationSnapshot,
        related_name="haat_calculations",
        on_delete=models.PROTECT,
    )
    supersedes = models.ForeignKey(
        "self",
        related_name="retries",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    calculation_state = models.CharField(max_length=16, choices=CalculationState.choices)
    method = models.CharField(max_length=80)
    method_version = models.CharField(max_length=80)
    radial_count = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(360)]
    )
    start_azimuth_deg = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("359.999"))],
    )
    sampling_interval_m = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100_000)]
    )
    inner_distance_m = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100_000)]
    )
    outer_distance_m = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100_000)]
    )
    rounding_m = models.DecimalField(
        max_digits=7,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001")), MaxValueValidator(Decimal("100"))],
    )
    antenna_agl_m = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(HEIGHT_MAX_M)],
    )
    site_elevation_m = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(HEIGHT_MIN_M), MaxValueValidator(HEIGHT_MAX_M)],
    )
    antenna_amsl_m = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(HEIGHT_MIN_M), MaxValueValidator(HEIGHT_MAX_M)],
    )
    average_terrain_m = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(HEIGHT_MIN_M), MaxValueValidator(HEIGHT_MAX_M)],
    )
    haat_m = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(HEIGHT_MIN_M), MaxValueValidator(HEIGHT_MAX_M)],
    )
    sample_count = models.PositiveIntegerField(default=0)
    excluded_sample_count = models.PositiveIntegerField(default=0)
    algorithm_snapshot = models.JSONField()
    exclusions = models.JSONField(default=list, blank=True)
    warnings = models.JSONField(default=list, blank=True)
    result_snapshot = models.JSONField()
    result_sha256 = models.CharField(max_length=64)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="created_haat_calculations",
        on_delete=models.PROTECT,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="approved_haat_calculations",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["incident", "site", "status"],
                name="rf_haat_inc_site_status_idx",
            )
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(outer_distance_m__gt=models.F("inner_distance_m")),
                name="rf_haat_outer_gt_inner",
            ),
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
                name="rf_haat_approval_consistent",
            ),
        ]

    def __str__(self):
        return f"{self.site}: {self.method_version} ({self.calculation_state})"

    def save(self, *args, **kwargs):
        if self.pk and HAATCalculation.objects.filter(pk=self.pk).exists():
            raise ValidationError("HAAT calculations are immutable after creation.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("HAAT calculations are retained.")

    @property
    def is_locked(self):
        return self.status == self.Status.APPROVED


class CoverageEstimate(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        APPROVED = "approved", "Approved"

    class CalculationState(models.TextChoices):
        COMPLETE = "complete", "Complete"
        UNSUPPORTED = "unsupported", "Unsupported"

    class Environment(models.TextChoices):
        OPEN = "open", "Open"
        RURAL = "rural", "Rural"
        SUBURBAN = "suburban", "Suburban"
        URBAN = "urban", "Urban"
        DENSE_URBAN = "dense_urban", "Dense urban"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.ForeignKey(
        Incident,
        related_name="coverage_estimates",
        on_delete=models.PROTECT,
    )
    site = models.ForeignKey(
        RadioSite,
        related_name="coverage_estimates",
        on_delete=models.PROTECT,
    )
    rf_input_snapshot = models.ForeignKey(
        RFAnalysisInputSnapshot,
        related_name="coverage_estimates",
        on_delete=models.PROTECT,
    )
    haat_calculation = models.ForeignKey(
        HAATCalculation,
        related_name="coverage_estimates",
        on_delete=models.PROTECT,
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    calculation_state = models.CharField(
        max_length=16,
        choices=CalculationState.choices,
    )
    environment = models.CharField(max_length=16, choices=Environment.choices)
    band = models.CharField(max_length=32)
    engine = models.CharField(max_length=120)
    engine_version = models.CharField(max_length=80)
    preset = models.CharField(max_length=80)
    preset_version = models.CharField(max_length=80)
    center_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    center_longitude = models.DecimalField(max_digits=9, decimal_places=6)
    nominal_distance_m = models.PositiveIntegerField(null=True, blank=True)
    conservative_distance_m = models.PositiveIntegerField(null=True, blank=True)
    optimistic_distance_m = models.PositiveIntegerField(null=True, blank=True)
    input_snapshot = models.JSONField()
    input_sha256 = models.CharField(max_length=64)
    model_snapshot = models.JSONField()
    warnings = models.JSONField(default=list, blank=True)
    exclusions = models.JSONField(default=list, blank=True)
    explanation = models.TextField()
    result_snapshot = models.JSONField()
    result_sha256 = models.CharField(max_length=64)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="created_coverage_estimates",
        on_delete=models.PROTECT,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="approved_coverage_estimates",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["incident", "site", "status"],
                name="rf_cov_inc_site_status_idx",
            )
        ]
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
                name="rf_cov_approval_consistent",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        calculation_state="complete",
                        nominal_distance_m__isnull=False,
                        conservative_distance_m__isnull=False,
                        optimistic_distance_m__isnull=False,
                    )
                    | models.Q(
                        calculation_state="unsupported",
                        nominal_distance_m__isnull=True,
                        conservative_distance_m__isnull=True,
                        optimistic_distance_m__isnull=True,
                    )
                ),
                name="rf_cov_distance_state_consistent",
            ),
        ]

    def __str__(self):
        return f"{self.site}: {self.engine_version} ({self.calculation_state})"

    def save(self, *args, **kwargs):
        if self.pk and CoverageEstimate.objects.filter(pk=self.pk).exists():
            raise ValidationError("Coverage estimates are immutable after creation.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Coverage estimates are retained.")

    @property
    def is_locked(self):
        return self.status == self.Status.APPROVED
