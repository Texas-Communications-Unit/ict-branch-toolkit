from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models


class Role(models.TextChoices):
    ADMINISTRATOR = "administrator", "Administrator"
    COML = "coml", "COML"
    COMC = "comc", "COMC"
    COMT = "comt", "COMT"
    CONTRIBUTOR = "contributor", "Contributor"
    READ_ONLY = "read_only", "Read-only"


class UserRoleAssignment(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        primary_key=True,
        related_name="toolkit_role",
        on_delete=models.CASCADE,
    )
    role = models.CharField(max_length=24, choices=Role.choices, default=Role.READ_ONLY)
    assigned_at = models.DateTimeField(auto_now=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="assigned_toolkit_roles",
        on_delete=models.PROTECT,
    )

    def __str__(self) -> str:
        return f"{self.user}: {self.get_role_display()}"


class ExternalIdentity(models.Model):
    """Local, non-password shadow identity for a future approved TX-COMU SSO provider."""

    class Eligibility(models.TextChoices):
        ELIGIBLE = "eligible", "Eligible"
        INELIGIBLE = "ineligible", "Ineligible"
        AMBIGUOUS = "ambiguous", "Ambiguous"
        STALE = "stale", "Stale"
        DISABLED = "disabled", "Disabled"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        primary_key=True,
        related_name="external_identity",
        on_delete=models.PROTECT,
    )
    provider = models.CharField(max_length=80)
    external_subject = models.CharField(max_length=200)
    civicrm_contact_id = models.CharField(max_length=80)
    eligibility = models.CharField(
        max_length=16,
        choices=Eligibility.choices,
        default=Eligibility.AMBIGUOUS,
    )
    mapped_role = models.CharField(
        max_length=24,
        choices=Role.choices,
        null=True,
        blank=True,
    )
    attributes_sha256 = models.CharField(
        max_length=64,
        validators=[
            RegexValidator(
                r"^[0-9a-f]{64}$",
                "Enter a lowercase SHA-256 digest.",
            )
        ],
    )
    last_refreshed_at = models.DateTimeField()
    valid_until = models.DateTimeField()
    disabled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "external_subject"],
                name="unique_external_identity_subject",
            ),
            models.UniqueConstraint(
                fields=["provider", "civicrm_contact_id"],
                name="unique_external_identity_civicrm_contact",
            ),
        ]
        indexes = [
            models.Index(fields=["provider", "eligibility", "valid_until"]),
        ]

    def __str__(self) -> str:
        return f"{self.provider}:{self.external_subject} -> {self.user_id}"
