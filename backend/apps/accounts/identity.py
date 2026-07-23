from dataclasses import dataclass
from typing import Protocol

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


@dataclass(frozen=True)
class IdentityRecord:
    external_id: str
    username: str
    email: str
    is_active: bool


class IdentityProvider(Protocol):
    def lookup(self, external_id: str) -> IdentityRecord | None: ...


class LocalIdentityProvider:
    def lookup(self, external_id: str) -> IdentityRecord | None:
        return None


def configured_identity_provider() -> IdentityProvider:
    if settings.ICT_IDENTITY_PROVIDER == "local":
        return LocalIdentityProvider()
    raise ImproperlyConfigured(
        "Only the local identity provider is implemented. External providers must use the "
        "replaceable IdentityProvider interface and remain optional."
    )
