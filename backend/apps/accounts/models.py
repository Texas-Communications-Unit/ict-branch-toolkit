from django.conf import settings
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
