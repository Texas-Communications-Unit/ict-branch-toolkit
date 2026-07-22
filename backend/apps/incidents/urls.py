from rest_framework.routers import DefaultRouter

from .views import IncidentViewSet, OperationalPeriodViewSet

router = DefaultRouter()
router.register("incidents", IncidentViewSet, basename="incident")
router.register("operational-periods", OperationalPeriodViewSet, basename="operational-period")

urlpatterns = router.urls
