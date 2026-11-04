from rest_framework.routers import DefaultRouter

from .views import AntennaStructureViewSet, FccDatasetStatusViewSet, UlsLicenseViewSet

router = DefaultRouter()
router.register("fcc-dataset-status", FccDatasetStatusViewSet, basename="fcc-dataset-status")
router.register(
    "fcc-antenna-structures",
    AntennaStructureViewSet,
    basename="fcc-antenna-structure",
)
router.register("fcc-licenses", UlsLicenseViewSet, basename="fcc-license")

urlpatterns = router.urls
