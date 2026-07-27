from rest_framework.routers import DefaultRouter

from .views import (
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

urlpatterns = router.urls
