from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CurrentUserView,
    ExternalIdentityStatusView,
    LocalContingencyAccountViewSet,
)

router = DefaultRouter()
router.register(
    "local-contingency-accounts",
    LocalContingencyAccountViewSet,
    basename="local-contingency-account",
)

urlpatterns = [
    path("me/", CurrentUserView.as_view(), name="current-user"),
    path(
        "external-identity/status/",
        ExternalIdentityStatusView.as_view(),
        name="external-identity-status",
    ),
    path("", include(router.urls)),
]
