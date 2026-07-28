from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    CoverageEngineStatusView,
    CoverageEstimateViewSet,
    DirectionalAnalysisStatusView,
    DirectionalCoverageAnalysisViewSet,
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
router.register(
    "coverage-estimates",
    CoverageEstimateViewSet,
    basename="coverage-estimate",
)
router.register(
    "directional-coverage-analyses",
    DirectionalCoverageAnalysisViewSet,
    basename="directional-coverage-analysis",
)

urlpatterns = [
    path(
        "elevation-provider/",
        ElevationProviderStatusView.as_view(),
        name="elevation-provider-status",
    ),
    path(
        "coverage-engine/",
        CoverageEngineStatusView.as_view(),
        name="coverage-engine-status",
    ),
    path(
        "directional-analysis-status/",
        DirectionalAnalysisStatusView.as_view(),
        name="directional-analysis-status",
    ),
    *router.urls,
]
