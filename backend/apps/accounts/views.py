from datetime import timedelta

from django.conf import settings
from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.audit.services import record_event

from .serializers import CurrentUserSerializer, TokenSessionSerializer


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
