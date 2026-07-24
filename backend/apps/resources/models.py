import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models

sha256_validator = RegexValidator(r"^[0-9a-f]{64}$", "Enter a lowercase SHA-256 digest.")


class ResourceSource(models.Model):
    class Type(models.TextChoices):
        SYNTHETIC = "synthetic", "Synthetic fixture"
        CISA_NIFOG = "cisa_nifog", "CISA NIFOG"
        CISA_AUXFOG = "cisa_auxfog", "CISA AUXFOG"
        CISA_STATE_FOG = "cisa_state_fog", "CISA state or regional FOG"
        LOCAL = "local", "Local controlled source"
        INCIDENT = "incident", "Incident-created source"
        OTHER = "other", "Other approved source"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=200)
    source_type = models.CharField(max_length=24, choices=Type.choices)
    authoritative_url = models.URLField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class ResourceRelease(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        EFFECTIVE = "effective", "Effective"
        SUPERSEDED = "superseded", "Superseded"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.ForeignKey(ResourceSource, related_name="releases", on_delete=models.PROTECT)
    version = models.CharField(max_length=80)
    released_on = models.DateField(null=True, blank=True)
    effective_status = models.CharField(max_length=16, choices=Status.choices)
    content_sha256 = models.CharField(max_length=64, validators=[sha256_validator])
    document_title = models.CharField(max_length=300, blank=True)
    publisher = models.CharField(max_length=200, blank=True)
    retrieved_on = models.DateField(null=True, blank=True)
    permitted_use = models.TextField(blank=True)
    transformation_method = models.TextField(blank=True)
    imported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-imported_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "version"], name="unique_source_release_version"
            )
        ]

    def __str__(self) -> str:
        return f"{self.source} {self.version}"


class ConventionalChannel(models.Model):
    class Mode(models.TextChoices):
        ANALOG_FM = "analog_fm", "Analog FM"
        P25 = "p25", "P25"
        DMR = "dmr", "DMR"
        NXDN = "nxdn", "NXDN"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    release = models.ForeignKey(
        ResourceRelease, related_name="conventional_channels", on_delete=models.PROTECT
    )
    identifier = models.CharField(max_length=80)
    name = models.CharField(max_length=160)
    channel_use = models.CharField(max_length=200, blank=True)
    band = models.CharField(max_length=40, blank=True)
    jurisdiction = models.CharField(max_length=80, blank=True)
    rx_frequency_hz = models.BigIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10_000_000_000)]
    )
    tx_frequency_hz = models.BigIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10_000_000_000)],
    )
    bandwidth_hz = models.PositiveIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(2_147_483_647)]
    )
    mode = models.CharField(max_length=20, choices=Mode.choices)
    rx_squelch = models.CharField(max_length=40, blank=True)
    tx_squelch = models.CharField(max_length=40, blank=True)
    emission_designator = models.CharField(max_length=40, blank=True)
    eligibility = models.TextField(blank=True)
    authorization = models.TextField(blank=True)
    source_section = models.CharField(max_length=240, blank=True)
    source_pages = models.CharField(max_length=80, blank=True)
    restrictions = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name", "identifier"]
        constraints = [
            models.UniqueConstraint(
                fields=["release", "identifier"], name="unique_conventional_identifier_release"
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.rx_frequency_hz} Hz)"


class TrunkedTalkgroup(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    release = models.ForeignKey(
        ResourceRelease, related_name="trunked_talkgroups", on_delete=models.PROTECT
    )
    identifier = models.CharField(max_length=80)
    name = models.CharField(max_length=160)
    system_name = models.CharField(max_length=160)
    talkgroup_id = models.PositiveIntegerField(validators=[MaxValueValidator(16_777_215)])
    mode = models.CharField(max_length=40, blank=True)
    eligibility = models.TextField(blank=True)
    authorization = models.TextField(blank=True)
    source_section = models.CharField(max_length=240, blank=True)
    source_pages = models.CharField(max_length=80, blank=True)
    restrictions = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["system_name", "name", "identifier"]
        constraints = [
            models.UniqueConstraint(
                fields=["release", "identifier"], name="unique_talkgroup_identifier_release"
            )
        ]

    def __str__(self) -> str:
        return f"{self.system_name}: {self.name} ({self.talkgroup_id})"


class ResourceImport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    release = models.OneToOneField(
        ResourceRelease, related_name="import_record", on_delete=models.PROTECT
    )
    imported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    payload_sha256 = models.CharField(max_length=64, validators=[sha256_validator])
    conventional_count = models.PositiveIntegerField()
    talkgroup_count = models.PositiveIntegerField()
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-imported_at"]

    def __str__(self) -> str:
        return f"Import of {self.release} at {self.imported_at}"
