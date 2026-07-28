from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import OfflinePackageViewSet, OfflineStatusView

router = DefaultRouter()
router.register("offline-packages", OfflinePackageViewSet, basename="offline-package")

urlpatterns = [
    path("offline-status/", OfflineStatusView.as_view(), name="offline-status"),
    path("", include(router.urls)),
]
