from django.urls import path

from .views import CurrentUserView, ExternalIdentityStatusView

urlpatterns = [
    path("me/", CurrentUserView.as_view(), name="current-user"),
    path(
        "external-identity/status/",
        ExternalIdentityStatusView.as_view(),
        name="external-identity-status",
    ),
]
