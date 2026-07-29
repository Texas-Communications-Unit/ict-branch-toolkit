from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    CollaborationChangeListView,
    CollaborationMutationView,
    ConflictResolutionView,
    PresenceView,
    SensitiveFieldRuleViewSet,
)

router = DefaultRouter()
router.register(
    "collaboration-sensitive-field-rules",
    SensitiveFieldRuleViewSet,
    basename="collaboration-sensitive-field-rule",
)

urlpatterns = [
    path(
        "collaboration/mutations/",
        CollaborationMutationView.as_view(),
        name="collaboration-mutation",
    ),
    path(
        "collaboration/changes/",
        CollaborationChangeListView.as_view(),
        name="collaboration-change-list",
    ),
    path(
        "collaboration/conflicts/<uuid:change_id>/resolve/",
        ConflictResolutionView.as_view(),
        name="collaboration-conflict-resolution",
    ),
    path(
        "collaboration/presence/",
        PresenceView.as_view(),
        name="collaboration-presence",
    ),
    *router.urls,
]
