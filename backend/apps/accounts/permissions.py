from rest_framework.permissions import BasePermission

from .policy import user_has_permission


class PolicyPermission(BasePermission):
    """Resolve API actions through the centralized role policy."""

    def _required(self, view):
        return getattr(view, "policy_actions", {}).get(getattr(view, "action", None))

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        required = self._required(view)
        action = getattr(view, "action", None)
        if action in {"retrieve", "update", "partial_update", "archive", "destroy"}:
            return True
        if action == "create" and getattr(view, "basename", None) in {
            "operational-period",
            "incident-membership",
        }:
            return True
        return required is None or user_has_permission(request.user, required)

    def has_object_permission(self, request, view, obj):
        required = self._required(view)
        if required is None:
            return True
        incident = obj if obj.__class__.__name__ == "Incident" else getattr(obj, "incident", None)
        if incident is None and hasattr(obj, "plan"):
            incident = obj.plan.incident
        if incident is None and hasattr(obj, "revision"):
            incident = obj.revision.plan.incident
        return user_has_permission(request.user, required, incident)


class LibraryImportPermission(BasePermission):
    def has_permission(self, request, view):
        from .policy import LIBRARY_IMPORT

        return user_has_permission(request.user, LIBRARY_IMPORT)
