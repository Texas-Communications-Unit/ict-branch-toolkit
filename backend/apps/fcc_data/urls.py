from rest_framework.routers import DefaultRouter

from .views import AntennaStructureViewSet, UlsLicenseViewSet

router = DefaultRouter()
router.register(
    "fcc-antenna-structures",
    AntennaStructureViewSet,
    basename="fcc-antenna-structure",
)
router.register("fcc-licenses", UlsLicenseViewSet, basename="fcc-license")

urlpatterns = router.urls
