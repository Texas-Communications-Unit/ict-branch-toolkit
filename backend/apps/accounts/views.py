from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.generics import RetrieveAPIView
from rest_framework.throttling import ScopedRateThrottle

from .serializers import CurrentUserSerializer


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
