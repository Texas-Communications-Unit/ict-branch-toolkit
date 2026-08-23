from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.accounts.views import (
    LocalContingencyActivationView,
    LogoutView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    ThrottledObtainAuthTokenView,
)
from apps.incidents.views import health

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/token/", ThrottledObtainAuthTokenView.as_view(), name="api-token"),
    path("api/auth/logout/", LogoutView.as_view(), name="api-logout"),
    path(
        "api/auth/password-reset/request/",
        PasswordResetRequestView.as_view(),
        name="api-password-reset-request",
    ),
    path(
        "api/auth/password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="api-password-reset-confirm",
    ),
    path(
        "api/auth/activate-local/",
        LocalContingencyActivationView.as_view(),
        name="api-activate-local",
    ),
    path("api/health/", health, name="health"),
    path("api/", include("apps.accounts.urls")),
    path("api/", include("apps.incidents.urls")),
    path("api/", include("apps.resources.urls")),
    path("api/", include("apps.fcc_data.urls")),
    path("api/", include("apps.plans.urls")),
    path("api/", include("apps.sites.urls")),
    path("api/", include("apps.rf_analysis.urls")),
    path("api/", include("apps.deconfliction.urls")),
    path("api/", include("apps.collaboration.urls")),
    path("api/", include("apps.extensions.urls")),
    path("api/", include("apps.inventory.urls")),
    path("api/", include("apps.audit.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
