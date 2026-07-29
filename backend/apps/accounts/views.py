import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.permissions import PolicyPermission
from apps.accounts.policy import ACCOUNT_MANAGE, role_for_user
from apps.audit.services import record_event

from .external_identity import identity_provider
from .models import LocalContingencyAccount, Role
from .serializers import (
    CurrentUserSerializer,
    ExternalIdentityStatusSerializer,
    LocalContingencyAccountCreateSerializer,
    LocalContingencyAccountSerializer,
    LocalContingencyActivationSerializer,
    TokenSessionSerializer,
)


class CurrentUserView(RetrieveAPIView):
    serializer_class = CurrentUserSerializer

    def get_object(self):
        return self.request.user


class ThrottledObtainAuthTokenView(ObtainAuthToken):
    """Rate-limit token issuance separately from, and more strictly than, the general API.

    Login is a credential-guessing target regardless of authentication state, so it is throttled
    by request rate alone (``ScopedRateThrottle`` keys anonymous requests by IP) rather than by
    the ``anon``/``user`` rates meant for ordinary API traffic.
    """

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    @extend_schema(auth=[], responses=TokenSessionSerializer)
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        try:
            local_account = user.local_contingency_account
        except LocalContingencyAccount.DoesNotExist:
            local_account = None
        if local_account and local_account.must_change_password:
            return Response(
                {
                    "code": "password_change_required",
                    "detail": "Activate this local contingency account before signing in.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        with transaction.atomic():
            Token.objects.filter(user=user).delete()
            token = Token.objects.create(user=user)
            expires_at = token.created + timedelta(seconds=settings.ICT_TOKEN_TTL_SECONDS)
            record_event(
                actor=user,
                action="authentication.login",
                target=user,
                details={"expires_at": expires_at.isoformat()},
            )
        return Response({"token": token.key, "expires_at": expires_at})


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={status.HTTP_204_NO_CONTENT: None})
    def post(self, request):
        with transaction.atomic():
            record_event(
                actor=request.user,
                action="authentication.logout",
                target=request.user,
            )
            request.auth.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ExternalIdentityStatusView(APIView):
    """Expose only capability/configuration state; never provider secrets or credentials."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses=ExternalIdentityStatusSerializer)
    def get(self, request):
        provider_status = identity_provider().status()
        return Response(
            {
                "provider": provider_status.provider,
                "enabled": provider_status.enabled,
                "protocol": provider_status.protocol,
                "authorization_code_flow": provider_status.authorization_code_flow,
                "password_passthrough": provider_status.password_passthrough,
                "live_connection": provider_status.live_connection,
                "warning": provider_status.warning,
                "break_glass_local_login_available": True,
                "eligibility_group": settings.ICT_EXTERNAL_ELIGIBILITY_GROUP,
                "role_field": settings.ICT_EXTERNAL_ROLE_FIELD,
                "identity_refresh_seconds": settings.ICT_EXTERNAL_IDENTITY_REFRESH_SECONDS,
                "outage_grace_seconds": settings.ICT_EXTERNAL_OUTAGE_GRACE_SECONDS,
                "allowed_roles": list(Role.values),
            }
        )


class LocalContingencyActivationView(APIView):
    authentication_classes = []
    permission_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    @extend_schema(auth=[], request=LocalContingencyActivationSerializer, responses={204: None})
    def post(self, request):
        serializer = LocalContingencyActivationSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        account = serializer.validated_data["account"]
        with transaction.atomic():
            user.set_password(serializer.validated_data["new_password"])
            user.save(update_fields=["password"])
            account.must_change_password = False
            account.save(update_fields=["must_change_password", "updated_at"])
            record_event(
                actor=user,
                action="local_contingency_account.activated",
                target=account,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class LocalContingencyAccountViewSet(viewsets.GenericViewSet):
    queryset = LocalContingencyAccount.objects.select_related(
        "user",
        "user__toolkit_role",
        "created_by",
        "disabled_by",
    )
    serializer_class = LocalContingencyAccountSerializer
    lookup_field = "user__username"
    lookup_url_kwarg = "username"
    permission_classes = [PolicyPermission]
    policy_actions = {
        "list": ACCOUNT_MANAGE,
        "create": ACCOUNT_MANAGE,
        "disable": ACCOUNT_MANAGE,
        "enable": ACCOUNT_MANAGE,
        "sign_out_all": ACCOUNT_MANAGE,
    }

    def get_queryset(self):
        return super().get_queryset().filter(is_synthetic_hidden=False)

    def list(self, request):
        return Response(self.get_serializer(self.get_queryset(), many=True).data)

    @transaction.atomic
    def create(self, request):
        temporary_password = secrets.token_urlsafe(24)
        input_serializer = LocalContingencyAccountCreateSerializer(
            data=request.data,
            context={
                "request": request,
                "temporary_password": temporary_password,
            },
        )
        input_serializer.is_valid(raise_exception=True)
        account = input_serializer.save()
        record_event(
            actor=request.user,
            action="local_contingency_account.created",
            target=account,
            details={
                "username": account.user.get_username(),
                "role": role_for_user(account.user),
                "reason": account.reason,
                "incident_ids": [
                    str(item)
                    for item in account.user.incident_memberships.values_list(
                        "incident_id", flat=True
                    )
                ],
                "temporary_credential_issued": True,
            },
        )
        return Response(
            {
                **self.get_serializer(account).data,
                "temporary_password": temporary_password,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def disable(self, request, username=None):
        account = self.get_object()
        reason = str(request.data.get("reason", "")).strip()
        if not reason:
            raise ValidationError({"reason": "Record why this account is being disabled."})
        account.user.is_active = False
        account.user.save(update_fields=["is_active"])
        Token.objects.filter(user=account.user).delete()
        account.disabled_at = timezone.now()
        account.disabled_by = request.user
        account.disabled_reason = reason
        account.save(
            update_fields=[
                "disabled_at",
                "disabled_by",
                "disabled_reason",
                "updated_at",
            ]
        )
        record_event(
            actor=request.user,
            action="local_contingency_account.disabled",
            target=account,
            details={"reason": reason, "sessions_revoked": True},
        )
        return Response(self.get_serializer(account).data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def enable(self, request, username=None):
        account = self.get_object()
        reason = str(request.data.get("reason", "")).strip()
        if not reason:
            raise ValidationError({"reason": "Record why this account is being enabled."})
        account.user.is_active = True
        account.user.save(update_fields=["is_active"])
        account.disabled_at = None
        account.disabled_by = None
        account.disabled_reason = ""
        account.save(
            update_fields=[
                "disabled_at",
                "disabled_by",
                "disabled_reason",
                "updated_at",
            ]
        )
        record_event(
            actor=request.user,
            action="local_contingency_account.enabled",
            target=account,
            details={"reason": reason},
        )
        return Response(self.get_serializer(account).data)

    @action(detail=True, methods=["post"], url_path="sign-out-all")
    @transaction.atomic
    def sign_out_all(self, request, username=None):
        account = self.get_object()
        revoked, _ = Token.objects.filter(user=account.user).delete()
        record_event(
            actor=request.user,
            action="local_contingency_account.sessions_revoked",
            target=account,
            details={"token_records_revoked": revoked},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
