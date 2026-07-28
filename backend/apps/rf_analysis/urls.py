from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ElevationProviderStatusView,
    ElevationSnapshotViewSet,
    HAATCalculationViewSet,
    RFAnalysisInputSnapshotViewSet,
    SubscriberProfileVersionViewSet,
    SubscriberProfileViewSet,
)

router = DefaultRouter()
router.register("subscriber-profiles", SubscriberProfileViewSet, basename="subscriber-profile")
router.register(
    "subscriber-profile-versions",
    SubscriberProfileVersionViewSet,
    basename="subscriber-profile-version",
)
router.register(
    "rf-analysis-input-snapshots",
    RFAnalysisInputSnapshotViewSet,
    basename="rf-analysis-input-snapshot",
)
router.register(
    "haat-calculations",
    HAATCalculationViewSet,
    basename="haat-calculation",
)
router.register(
    "elevation-snapshots",
    ElevationSnapshotViewSet,
    basename="elevation-snapshot",
)

urlpatterns = [
    path(
        "elevation-provider/",
        ElevationProviderStatusView.as_view(),
        name="elevation-provider-status",
    ),
    *router.urls,
]
