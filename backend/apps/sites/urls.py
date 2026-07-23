from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    CoordinateParseView,
    GeocoderSearchView,
    ManualRingViewSet,
    RadioSiteViewSet,
    SiteAssignmentViewSet,
    SpatialExportView,
)

router = DefaultRouter()
router.register("radio-sites", RadioSiteViewSet, basename="radio-site")
router.register("manual-rings", ManualRingViewSet, basename="manual-ring")
router.register("site-assignments", SiteAssignmentViewSet, basename="site-assignment")

urlpatterns = [
    path("coordinates/parse/", CoordinateParseView.as_view(), name="coordinate-parse"),
    path("geocoder/search/", GeocoderSearchView.as_view(), name="geocoder-search"),
    path(
        "spatial-exports/<uuid:revision_id>/<str:export_format>/",
        SpatialExportView.as_view(),
        name="spatial-export",
    ),
    *router.urls,
]
