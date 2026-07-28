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
        CACHE = "cache", "Cache"
        GATEWAY = "gateway", "Gateway"
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


class DirectionalCoverageAnalysis(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        APPROVED = "approved", "Approved"

    class CalculationState(models.TextChoices):
        COMPLETE = "complete", "Complete"
        UNSUPPORTED = "unsupported", "Unsupported"
        NO_OVERLAP = "no_overlap", "No probable two-way overlap"

    class LimitingPath(models.TextChoices):
        TALK_OUT = "talk_out", "Talk-out"
        TALK_IN = "talk_in", "Talk-in"
        EQUAL = "equal", "Equal"
        NONE = "none", "Not available"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.ForeignKey(
        Incident,
        related_name="directional_coverage_analyses",
        on_delete=models.PROTECT,
    )
    site = models.ForeignKey(
        RadioSite,
        related_name="directional_coverage_analyses",
        on_delete=models.PROTECT,
    )
    infrastructure_rf_input_snapshot = models.ForeignKey(
        RFAnalysisInputSnapshot,
        related_name="infrastructure_directional_analyses",
        on_delete=models.PROTECT,
    )
    subscriber_rf_input_snapshot = models.ForeignKey(
        RFAnalysisInputSnapshot,
        related_name="subscriber_directional_analyses",
        on_delete=models.PROTECT,
    )
    haat_calculation = models.ForeignKey(
        HAATCalculation,
        related_name="directional_coverage_analyses",
        on_delete=models.PROTECT,
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    calculation_state = models.CharField(
        max_length=16,
        choices=CalculationState.choices,
    )
    environment = models.CharField(max_length=16, choices=CoverageEstimate.Environment.choices)
    engine = models.CharField(max_length=120)
    engine_version = models.CharField(max_length=80)
    preset = models.CharField(max_length=80)
    preset_version = models.CharField(max_length=80)
    rule_version = models.CharField(max_length=80)
    center_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    center_longitude = models.DecimalField(max_digits=9, decimal_places=6)
    talk_out_distance_m = models.PositiveIntegerField(null=True, blank=True)
    talk_in_distance_m = models.PositiveIntegerField(null=True, blank=True)
    probable_two_way_distance_m = models.PositiveIntegerField(null=True, blank=True)
    limiting_path = models.CharField(max_length=12, choices=LimitingPath.choices)
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
        related_name="created_directional_coverage_analyses",
        on_delete=models.PROTECT,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="approved_directional_coverage_analyses",
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
                name="rf_dir_inc_site_status_idx",
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
                name="rf_dir_approval_consistent",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        calculation_state="complete",
                        talk_out_distance_m__isnull=False,
                        talk_in_distance_m__isnull=False,
                        probable_two_way_distance_m__isnull=False,
                    )
                    | models.Q(
                        calculation_state__in=["unsupported", "no_overlap"],
                        probable_two_way_distance_m__isnull=True,
                    )
                ),
                name="rf_dir_distance_state_consistent",
            ),
        ]

    def __str__(self):
        return f"{self.site}: {self.rule_version} ({self.calculation_state}; {self.limiting_path})"

    def save(self, *args, **kwargs):
        if self.pk and DirectionalCoverageAnalysis.objects.filter(pk=self.pk).exists():
            raise ValidationError("Directional coverage analyses are immutable after creation.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Directional coverage analyses are retained.")

    @property
    def is_locked(self):
        return self.status == self.Status.APPROVED


class FieldObservation(models.Model):
    class Classification(models.TextChoices):
        GOOD = "good", "Good communications"
        MARGINAL = "marginal", "Marginal communications"
        FAILED = "failed", "Failed communications"

    class EvidenceType(models.TextChoices):
        MEASURED = "measured", "Measured value"
        OPERATOR = "operator", "Operator judgment"
        IMPORTED = "imported", "Imported record"
        MODELED = "modeled", "Modeled value"

    class LocationPrecision(models.TextChoices):
        EXACT = "exact", "Exact"
        GENERALIZED = "generalized", "Generalized"
        REDACTED = "redacted", "Redacted"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.ForeignKey(
        Incident,
        related_name="field_observations",
        on_delete=models.PROTECT,
    )
    infrastructure_rf_input_snapshot = models.ForeignKey(
        RFAnalysisInputSnapshot,
        related_name="infrastructure_field_observations",
        on_delete=models.PROTECT,
    )
    subscriber_rf_input_snapshot = models.ForeignKey(
        RFAnalysisInputSnapshot,
        related_name="subscriber_field_observations",
        on_delete=models.PROTECT,
    )
    coverage_estimate = models.ForeignKey(
        CoverageEstimate,
        related_name="field_observations",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    directional_analysis = models.ForeignKey(
        DirectionalCoverageAnalysis,
        related_name="field_observations",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    supersedes = models.OneToOneField(
        "self",
        related_name="superseded_by",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    classification = models.CharField(max_length=12, choices=Classification.choices)
    evidence_type = models.CharField(max_length=12, choices=EvidenceType.choices)
    observed_from = models.DateTimeField()
    observed_to = models.DateTimeField()
    location_precision = models.CharField(
        max_length=12,
        choices=LocationPrecision.choices,
    )
    coordinate_reference = models.CharField(max_length=32, default="EPSG:4326")
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("-90")), MaxValueValidator(Decimal("90"))],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("-180")), MaxValueValidator(Decimal("180"))],
    )
    location_precision_m = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(1_000_000)],
    )
    direction_degrees = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("359.999"))],
    )
    path_distance_m = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(1_000_000)],
    )
    observer_source = models.CharField(max_length=160)
    collection_method = models.CharField(max_length=120)
    environment = models.JSONField(default=dict, blank=True)
    measurements = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    quality_flags = models.JSONField(default=list, blank=True)
    source_record_id = models.CharField(max_length=160, blank=True)
    source_revision = models.CharField(max_length=160)
    input_snapshot = models.JSONField()
    input_sha256 = models.CharField(max_length=64)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="created_field_observations",
        on_delete=models.PROTECT,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-observed_to", "-created_at"]
        indexes = [
            models.Index(
                fields=["incident", "classification", "evidence_type"],
                name="rf_obs_inc_class_type_idx",
            ),
            models.Index(
                fields=["incident", "observed_to"],
                name="rf_obs_inc_observed_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(observed_to__gte=models.F("observed_from")),
                name="rf_obs_window_ordered",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        location_precision="redacted",
                        latitude__isnull=True,
                        longitude__isnull=True,
                        location_precision_m__isnull=True,
                    )
                    | (
                        models.Q(
                            location_precision__in=["exact", "generalized"],
                            latitude__isnull=False,
                            longitude__isnull=False,
                            location_precision_m__isnull=False,
                        )
                    )
                ),
                name="rf_obs_location_consistent",
            ),
        ]

    def __str__(self):
        return f"{self.incident}: {self.classification} at {self.observed_to.isoformat()}"

    def save(self, *args, **kwargs):
        if self.pk and FieldObservation.objects.filter(pk=self.pk).exists():
            raise ValidationError("Field observations are immutable; create a superseding record.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Field observations are retained.")

    @property
    def current_review_state(self):
        review = self.reviews.order_by("-created_at", "-id").first()
        return review.decision if review else "pending"


class FieldObservationReview(models.Model):
    class Decision(models.TextChoices):
        APPROVED = "approved", "Approved"
        EXCLUDED = "excluded", "Excluded"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    observation = models.ForeignKey(
        FieldObservation,
        related_name="reviews",
        on_delete=models.PROTECT,
    )
    decision = models.CharField(max_length=12, choices=Decision.choices)
    reason = models.TextField()
    evidence_sha256 = models.CharField(max_length=64)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="field_observation_reviews",
        on_delete=models.PROTECT,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["observation", "created_at", "id"]
        indexes = [
            models.Index(
                fields=["observation", "created_at"],
                name="rf_obs_review_history_idx",
            )
        ]

    def __str__(self):
        return f"{self.observation}: {self.decision}"

    def save(self, *args, **kwargs):
        if self.pk and FieldObservationReview.objects.filter(pk=self.pk).exists():
            raise ValidationError("Observation review decisions are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Observation review decisions are retained.")


class CalibrationSet(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        APPROVED = "approved", "Approved"

    class CalculationState(models.TextChoices):
        COMPLETE = "complete", "Complete"
        INSUFFICIENT_DATA = "insufficient_data", "Insufficient data"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.ForeignKey(
        Incident,
        related_name="calibration_sets",
        on_delete=models.PROTECT,
    )
    name = models.CharField(max_length=160)
    version = models.PositiveIntegerField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    calculation_state = models.CharField(
        max_length=24,
        choices=CalculationState.choices,
    )
    algorithm = models.CharField(max_length=120)
    algorithm_version = models.CharField(max_length=120)
    parameters = models.JSONField()
    baseline_preset = models.CharField(max_length=80)
    baseline_preset_version = models.CharField(max_length=80)
    observation_snapshot = models.JSONField()
    observation_sha256 = models.CharField(max_length=64)
    recommended_preset = models.JSONField()
    before_after = models.JSONField()
    warnings = models.JSONField(default=list, blank=True)
    exclusions = models.JSONField(default=list, blank=True)
    result_snapshot = models.JSONField()
    result_sha256 = models.CharField(max_length=64)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="created_calibration_sets",
        on_delete=models.PROTECT,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="approved_calibration_sets",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    observations = models.ManyToManyField(
        FieldObservation,
        related_name="calibration_sets",
        through="CalibrationSetObservation",
    )

    class Meta:
        ordering = ["incident", "name", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["incident", "name", "version"],
                name="rf_calibration_name_version_unique",
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
                name="rf_calibration_approval_consistent",
            ),
        ]

    def __str__(self):
        return f"{self.incident}: {self.name} v{self.version}"

    def save(self, *args, **kwargs):
        if self.pk and CalibrationSet.objects.filter(pk=self.pk).exists():
            raise ValidationError("Calibration sets are immutable after creation.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Calibration sets are retained.")

    @property
    def is_locked(self):
        return self.status == self.Status.APPROVED


class CalibrationSetObservation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    calibration_set = models.ForeignKey(
        CalibrationSet,
        related_name="observation_links",
        on_delete=models.PROTECT,
    )
    observation = models.ForeignKey(
        FieldObservation,
        related_name="calibration_links",
        on_delete=models.PROTECT,
    )
    observation_sha256 = models.CharField(max_length=64)
    review_evidence_sha256 = models.CharField(max_length=64)
    position = models.PositiveIntegerField()

    class Meta:
        ordering = ["calibration_set", "position"]
        constraints = [
            models.UniqueConstraint(
                fields=["calibration_set", "observation"],
                name="rf_calibration_observation_unique",
            ),
            models.UniqueConstraint(
                fields=["calibration_set", "position"],
                name="rf_calibration_position_unique",
            ),
        ]

    def __str__(self):
        return f"{self.calibration_set}: observation {self.position}"

    def save(self, *args, **kwargs):
        if self.pk and CalibrationSetObservation.objects.filter(pk=self.pk).exists():
            raise ValidationError("Calibration set membership is immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Calibration set membership is retained.")


class Phase2ValidationBundle(models.Model):
    """Retained, version-pinned evidence for a Phase 2 release-candidate check.

    Source selections and completed evidence are immutable. Only explicit job
    lifecycle and approval fields may change after the row is queued.
    """

    class JobState(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        COMPLETE = "complete", "Complete"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        APPROVED = "approved", "Approved"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.ForeignKey(
        Incident,
        related_name="phase2_validation_bundles",
        on_delete=models.PROTECT,
    )
    approved_revision = models.ForeignKey(
        "plans.PlanRevision",
        related_name="phase2_validation_bundles",
        on_delete=models.PROTECT,
    )
    haat_calculation = models.ForeignKey(
        HAATCalculation,
        related_name="phase2_validation_bundles",
        on_delete=models.PROTECT,
    )
    coverage_estimate = models.ForeignKey(
        CoverageEstimate,
        related_name="phase2_validation_bundles",
        on_delete=models.PROTECT,
    )
    directional_analysis = models.ForeignKey(
        DirectionalCoverageAnalysis,
        related_name="phase2_validation_bundles",
        on_delete=models.PROTECT,
    )
    calibration_set = models.ForeignKey(
        CalibrationSet,
        related_name="phase2_validation_bundles",
        on_delete=models.PROTECT,
    )
    supersedes = models.ForeignKey(
        "self",
        related_name="retries",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    validation_profile_id = models.CharField(max_length=80)
    validation_profile_version = models.CharField(max_length=120)
    app_version = models.CharField(max_length=80)
    job_state = models.CharField(
        max_length=12,
        choices=JobState.choices,
        default=JobState.QUEUED,
    )
    progress_step = models.CharField(max_length=80, default="queued")
    progress_percent = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    input_snapshot = models.JSONField()
    input_sha256 = models.CharField(max_length=64)
    result_snapshot = models.JSONField(default=dict, blank=True)
    result_sha256 = models.CharField(max_length=64, blank=True)
    failure_code = models.CharField(max_length=80, blank=True)
    failure_message = models.CharField(max_length=240, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="created_phase2_validation_bundles",
        on_delete=models.PROTECT,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="approved_phase2_validation_bundles",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["incident", "job_state"],
                name="rf_p2val_inc_state_idx",
            ),
            models.Index(
                fields=["incident", "status"],
                name="rf_p2val_inc_status_idx",
            ),
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
                name="rf_p2val_approval_consistent",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        job_state="queued",
                        started_at__isnull=True,
                        completed_at__isnull=True,
                        progress_percent=0,
                    )
                    | models.Q(
                        job_state="running",
                        started_at__isnull=False,
                        completed_at__isnull=True,
                    )
                    | models.Q(
                        job_state__in=["complete", "failed", "cancelled"],
                        completed_at__isnull=False,
                    )
                ),
                name="rf_p2val_job_state_consistent",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        job_state="complete",
                    )
                    & ~models.Q(result_sha256="")
                    | ~models.Q(job_state="complete")
                ),
                name="rf_p2val_complete_has_digest",
            ),
        ]

    def __str__(self):
        return (
            f"{self.incident}: {self.validation_profile_version} ({self.job_state}; {self.status})"
        )

    def save(self, *args, **kwargs):
        if self.pk:
            previous = Phase2ValidationBundle.objects.filter(pk=self.pk).first()
            if previous:
                immutable_fields = (
                    "incident_id",
                    "approved_revision_id",
                    "haat_calculation_id",
                    "coverage_estimate_id",
                    "directional_analysis_id",
                    "calibration_set_id",
                    "supersedes_id",
                    "validation_profile_id",
                    "validation_profile_version",
                    "app_version",
                    "input_snapshot",
                    "input_sha256",
                    "created_by_id",
                )
                if any(
                    getattr(self, field) != getattr(previous, field) for field in immutable_fields
                ):
                    raise ValidationError(
                        "Phase 2 validation source selections and inputs are immutable."
                    )
                if previous.job_state in {
                    self.JobState.COMPLETE,
                    self.JobState.FAILED,
                    self.JobState.CANCELLED,
                }:
                    terminal_fields = (
                        "job_state",
                        "progress_step",
                        "progress_percent",
                        "result_snapshot",
                        "result_sha256",
                        "failure_code",
                        "failure_message",
                        "started_at",
                        "completed_at",
                    )
                    if any(
                        getattr(self, field) != getattr(previous, field)
                        for field in terminal_fields
                    ):
                        raise ValidationError("Completed Phase 2 validation evidence is immutable.")
                if previous.status == self.Status.APPROVED:
                    raise ValidationError("Approved Phase 2 validation bundles are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Phase 2 validation bundles are retained.")

    @property
    def is_locked(self):
        return self.status == self.Status.APPROVED
