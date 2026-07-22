from rest_framework.permissions import SAFE_METHODS, BasePermission


class AdminWriteAuthenticatedRead(BasePermission):
    """P1.0 policy: authenticated users read; administrators mutate."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.method in SAFE_METHODS or request.user.is_staff
