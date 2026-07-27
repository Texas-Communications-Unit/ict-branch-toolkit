from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed


class ExpiringTokenAuthentication(TokenAuthentication):
    """Reject local prototype tokens after the configured maximum lifetime."""

    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)
        expires_at = token.created + timedelta(seconds=settings.ICT_TOKEN_TTL_SECONDS)
        if timezone.now() >= expires_at:
            raise AuthenticationFailed("Token has expired.")
        return user, token
