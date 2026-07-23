from rest_framework.routers import DefaultRouter

from .views import AssignmentViewSet, PlanViewSet, RelationshipViewSet, RevisionViewSet

router = DefaultRouter()
router.register("ics205-plans", PlanViewSet, basename="ics205-plan")
router.register("plan-revisions", RevisionViewSet, basename="plan-revision")
router.register("plan-assignments", AssignmentViewSet, basename="plan-assignment")
router.register("plan-relationships", RelationshipViewSet, basename="plan-relationship")

urlpatterns = router.urls
