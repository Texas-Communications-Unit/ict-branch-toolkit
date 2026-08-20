from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


class EmailDeliveryUnavailable(RuntimeError):
    pass


def send_password_reset_email(user) -> None:
    if not settings.ICT_EMAIL_ENABLED:
        raise EmailDeliveryUnavailable(
            "Email delivery is not configured. Set ICT_EMAIL_ENABLED and the SMTP settings."
        )
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    query = urlencode({"reset_uid": uid, "reset_token": token})
    reset_url = f"{settings.ICT_PUBLIC_BASE_URL}/?{query}"
    send_mail(
        subject="ICT Branch Toolkit password setup or reset",
        message=(
            f"Hello {user.get_full_name() or user.get_username()},\n\n"
            f"Your ICT Branch Toolkit username is: {user.get_username()}\n\n"
            "Use the time-limited link below to choose a password. The link can be used only "
            f"once and expires in {settings.PASSWORD_RESET_TIMEOUT // 60} minutes.\n\n"
            f"{reset_url}\n\n"
            "If you did not request this message, contact your toolkit administrator."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )
