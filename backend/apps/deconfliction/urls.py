from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import DeconflictionAnalysisViewSet, DeconflictionRuleSetStatusView

router = DefaultRouter()
router.register(
    "deconfliction-analyses",
    DeconflictionAnalysisViewSet,
    basename="deconfliction-analysis",
)

urlpatterns = [
    path(
        "deconfliction-status/",
        DeconflictionRuleSetStatusView.as_view(),
        name="deconfliction-status",
    ),
    *router.urls,
]
