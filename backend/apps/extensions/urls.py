from django.urls import path
from rest_framework.routers import DefaultRouter

from .ics205b_views import ICS205BAssignmentViewSet, ICS205BFormViewSet
from .views import (
    ExtensionCatalogView,
    ExtensionDisableView,
    ExtensionEnableView,
    ExtensionExecutionViewSet,
    ExtensionInstallView,
)

router = DefaultRouter()
router.register(
    "extension-executions",
    ExtensionExecutionViewSet,
    basename="extension-execution",
)
router.register("ics205b-forms", ICS205BFormViewSet, basename="ics205b-form")
router.register(
    "ics205b-assignments",
    ICS205BAssignmentViewSet,
    basename="ics205b-assignment",
)

urlpatterns = [
    path("extensions/", ExtensionCatalogView.as_view(), name="extension-catalog"),
    path("extensions/install/", ExtensionInstallView.as_view(), name="extension-install"),
    path(
        "extensions/<slug:extension_key>/enable/",
        ExtensionEnableView.as_view(),
        name="extension-enable",
    ),
    path(
        "extensions/<slug:extension_key>/disable/",
        ExtensionDisableView.as_view(),
        name="extension-disable",
    ),
    *router.urls,
]
