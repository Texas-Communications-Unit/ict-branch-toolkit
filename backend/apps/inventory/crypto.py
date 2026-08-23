import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def _key() -> bytes:
    configured = settings.ICT_INVENTORY_ENCRYPTION_KEY
    try:
        key = base64.urlsafe_b64decode(configured.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise ImproperlyConfigured("ICT_INVENTORY_ENCRYPTION_KEY must be URL-safe base64.") from exc
    if len(key) != 32:
        raise ImproperlyConfigured("ICT_INVENTORY_ENCRYPTION_KEY must encode exactly 32 bytes.")
    return key


def encrypt_value(value: str, *, context: str) -> str:
    nonce = os.urandom(12)
    ciphertext = AESGCM(_key()).encrypt(nonce, value.encode("utf-8"), context.encode("utf-8"))
    return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def decrypt_value(value: str, *, context: str) -> str:
    payload = base64.urlsafe_b64decode(value.encode("ascii"))
    return (
        AESGCM(_key()).decrypt(payload[:12], payload[12:], context.encode("utf-8")).decode("utf-8")
    )
