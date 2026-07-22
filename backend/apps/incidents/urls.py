from rest_framework.routers import DefaultRouter

from .views import IncidentMembershipViewSet, IncidentViewSet, OperationalPeriodViewSet

router = DefaultRouter()
router.register("incidents", IncidentViewSet, basename="incident")
router.register("operational-periods", OperationalPeriodViewSet, basename="operational-period")
router.register("incident-memberships", IncidentMembershipViewSet, basename="incident-membership")

urlpatterns = router.urls
