import hashlib
import json
from dataclasses import dataclass
from datetime import datetime

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils import timezone
from django.utils.module_loading import import_string
from rest_framework.exceptions import APIException

from apps.audit.services import record_event

from .models import ExternalIdentity, Role, UserRoleAssignment


class IdentityProviderUnavailable(APIException):
    status_code = 503
    default_detail = (
        "TX-COMU single sign-on is unavailable. Use only the separately authorized "
        "break-glass path during an approved identity-provider outage."
    )
    default_code = "identity_provider_unavailable"


@dataclass(frozen=True)
class IdentityProviderStatus:
    provider: str
    enabled: bool
    protocol: str
    authorization_code_flow: bool
    password_passthrough: bool
    live_connection: bool
    warning: str


@dataclass(frozen=True)
class ExternalIdentityAssertion:
    provider: str
    external_subject: str
    civicrm_contact_id: str
    display_name: str
    eligible: bool
    role_keys: tuple[str, ...]
    valid_until: datetime


class DisabledExternalIdentityProvider:
    """Fail-closed placeholder. This class performs no network or credential operation."""

    name = "disabled"

    def status(self) -> IdentityProviderStatus:
        return IdentityProviderStatus(
            provider=self.name,
            enabled=False,
            protocol="authorization_code",
            authorization_code_flow=False,
            password_passthrough=False,
            live_connection=False,
            warning=(
                "External TX-COMU identity is disabled until issuer, audience, redirect, "
                "role mapping, session, outage, revocation, and break-glass controls are approved."
            ),
        )

    def begin_authorization(self, *, request):
        raise IdentityProviderUnavailable()

    def exchange_code(self, *, code, state, nonce, redirect_uri):
        raise IdentityProviderUnavailable()

    def refresh_identity(self, *, external_subject):
        raise IdentityProviderUnavailable()


def identity_provider():
    try:
        provider_class = import_string(settings.ICT_EXTERNAL_IDENTITY_PROVIDER)
    except (ImportError, AttributeError) as exc:
        raise ImproperlyConfigured("ICT_EXTERNAL_IDENTITY_PROVIDER cannot be imported.") from exc
    provider = provider_class()
    required = {"status", "begin_authorization", "exchange_code", "refresh_identity"}
    if not all(callable(getattr(provider, name, None)) for name in required):
        raise ImproperlyConfigured(
            "The external identity provider does not implement the required interface."
        )
    return provider


def _mapped_role(role_keys: tuple[str, ...]) -> str | None:
    matched = {
        role
        for role, configured_keys in settings.ICT_EXTERNAL_ROLE_MAPPINGS.items()
        if role in Role.values
        and isinstance(configured_keys, list)
        and set(map(str, configured_keys)).intersection(role_keys)
    }
    return matched.pop() if len(matched) == 1 else None


@transaction.atomic
def provision_shadow_identity(assertion: ExternalIdentityAssertion) -> ExternalIdentity:
    """Provision a local shadow only after a future provider has validated its assertion."""

    if not settings.ICT_EXTERNAL_SSO_ENABLED:
        raise IdentityProviderUnavailable()
    if not assertion.external_subject or not assertion.civicrm_contact_id:
        raise ValueError("Stable external subject and CiviCRM contact identifiers are required.")
    if assertion.valid_until <= timezone.now():
        raise ValueError("The external identity assertion has expired.")

    role = _mapped_role(assertion.role_keys) if assertion.eligible else None
    eligibility = (
        ExternalIdentity.Eligibility.ELIGIBLE
        if assertion.eligible and role
        else (
            ExternalIdentity.Eligibility.AMBIGUOUS
            if assertion.eligible
            else ExternalIdentity.Eligibility.INELIGIBLE
        )
    )
    existing_subject = (
        ExternalIdentity.objects.filter(
            provider=assertion.provider,
            external_subject=assertion.external_subject,
        )
        .select_related("user")
        .first()
    )
    existing_contact = (
        ExternalIdentity.objects.filter(
            provider=assertion.provider,
            civicrm_contact_id=assertion.civicrm_contact_id,
        )
        .select_related("user")
        .first()
    )
    if existing_subject and existing_contact and existing_subject.pk != existing_contact.pk:
        raise ValueError("External subject and CiviCRM contact resolve to different identities.")
    identity = existing_subject or existing_contact
    user_model = get_user_model()
    created = identity is None
    if created:
        username_digest = hashlib.sha256(
            f"{assertion.provider}:{assertion.external_subject}".encode()
        ).hexdigest()[:24]
        user = user_model(username=f"txcomu_{username_digest}")
        user.set_unusable_password()
    else:
        user = identity.user

    user.first_name = assertion.display_name[:150]
    user.last_name = ""
    user.is_active = eligibility == ExternalIdentity.Eligibility.ELIGIBLE
    user.save()
    attributes = {
        "provider": assertion.provider,
        "external_subject": assertion.external_subject,
        "civicrm_contact_id": assertion.civicrm_contact_id,
        "eligible": assertion.eligible,
        "role_keys": sorted(assertion.role_keys),
        "mapped_role": role,
        "valid_until": assertion.valid_until.isoformat(),
    }
    attributes_sha256 = hashlib.sha256(
        json.dumps(attributes, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    identity, _ = ExternalIdentity.objects.update_or_create(
        user=user,
        defaults={
            "provider": assertion.provider,
            "external_subject": assertion.external_subject,
            "civicrm_contact_id": assertion.civicrm_contact_id,
            "eligibility": eligibility,
            "mapped_role": role,
            "attributes_sha256": attributes_sha256,
            "last_refreshed_at": timezone.now(),
            "valid_until": assertion.valid_until,
            "disabled_at": None if user.is_active else timezone.now(),
        },
    )
    if role:
        UserRoleAssignment.objects.update_or_create(
            user=user,
            defaults={"role": role, "assigned_by": None},
        )
    else:
        UserRoleAssignment.objects.filter(user=user).delete()
    if not user.is_active and hasattr(user, "auth_token"):
        user.auth_token.delete()
    record_event(
        actor=user,
        action=(
            "external_identity.shadow_created" if created else "external_identity.shadow_updated"
        ),
        target=identity,
        details={
            "provider": assertion.provider,
            "eligibility": eligibility,
            "mapped_role": role,
            "attributes_sha256": attributes_sha256,
            "valid_until": assertion.valid_until.isoformat(),
        },
    )
    return identity
