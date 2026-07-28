from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ChannelImportView,
    ConventionalChannelViewSet,
    RadioReferenceProviderStatusView,
    ResourceReleaseViewSet,
    TrunkedTalkgroupViewSet,
)

router = DefaultRouter()
router.register("resource-releases", ResourceReleaseViewSet, basename="resource-release")
router.register(
    "conventional-channels", ConventionalChannelViewSet, basename="conventional-channel"
)
router.register("trunked-talkgroups", TrunkedTalkgroupViewSet, basename="trunked-talkgroup")

urlpatterns = [
    path("channel-imports/", ChannelImportView.as_view(), name="channel-import"),
    path(
        "radioreference-provider/",
        RadioReferenceProviderStatusView.as_view(),
        name="radioreference-provider",
    ),
]
urlpatterns += router.urls
