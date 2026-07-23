from __future__ import annotations

from collections.abc import Iterable

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

from .models import Role

INCIDENT_VIEW = "incident.view"
INCIDENT_CREATE = "incident.create"
INCIDENT_CHANGE = "incident.change"
INCIDENT_ARCHIVE = "incident.archive"
MEMBERSHIP_MANAGE = "incident.membership.manage"
PERIOD_CREATE = "period.create"
PERIOD_CHANGE = "period.change"
PERIOD_ARCHIVE = "period.archive"
LIBRARY_VIEW = "library.view"
LIBRARY_IMPORT = "library.import"
ACCOUNT_MANAGE = "account.manage"
AUDIT_VIEW = "audit.view"

DEFAULT_ROLE_POLICY = {
    Role.ADMINISTRATOR: {
        INCIDENT_VIEW,
        INCIDENT_CREATE,
        INCIDENT_CHANGE,
        INCIDENT_ARCHIVE,
        MEMBERSHIP_MANAGE,
        PERIOD_CREATE,
        PERIOD_CHANGE,
        PERIOD_ARCHIVE,
        LIBRARY_VIEW,
        LIBRARY_IMPORT,
        ACCOUNT_MANAGE,
        AUDIT_VIEW,
    },
    Role.COML: {
        INCIDENT_VIEW,
        INCIDENT_CREATE,
        INCIDENT_CHANGE,
        INCIDENT_ARCHIVE,
        MEMBERSHIP_MANAGE,
        PERIOD_CREATE,
        PERIOD_CHANGE,
        PERIOD_ARCHIVE,
        LIBRARY_VIEW,
    },
    Role.COMC: {
        INCIDENT_VIEW,
        INCIDENT_CREATE,
        INCIDENT_CHANGE,
        INCIDENT_ARCHIVE,
        MEMBERSHIP_MANAGE,
        PERIOD_CREATE,
        PERIOD_CHANGE,
        PERIOD_ARCHIVE,
        LIBRARY_VIEW,
    },
    Role.COMT: {
        INCIDENT_VIEW,
        INCIDENT_CHANGE,
        PERIOD_CREATE,
        PERIOD_CHANGE,
        PERIOD_ARCHIVE,
        LIBRARY_VIEW,
    },
    Role.CONTRIBUTOR: {
        INCIDENT_VIEW,
        INCIDENT_CHANGE,
        PERIOD_CREATE,
        PERIOD_CHANGE,
        LIBRARY_VIEW,
    },
    Role.READ_ONLY: {INCIDENT_VIEW, LIBRARY_VIEW},
}


def role_for_user(user) -> str:
    if user.is_superuser:
        return Role.ADMINISTRATOR
    try:
        return user.toolkit_role.role
    except (AttributeError, ObjectDoesNotExist):
        return Role.READ_ONLY


def _configured_policy() -> dict[str, set[str]]:
    policy = {role: set(permissions) for role, permissions in DEFAULT_ROLE_POLICY.items()}
    for role, permissions in settings.ICT_ROLE_POLICY_OVERRIDES.items():
        if role in Role.values and isinstance(permissions, list):
            policy[role] = {str(permission) for permission in permissions}
    return policy


def permissions_for_role(role: str) -> set[str]:
    return _configured_policy().get(role, set())


def permissions_for_user(user, incident=None) -> set[str]:
    permissions = permissions_for_role(role_for_user(user))
    if incident is None or role_for_user(user) == Role.ADMINISTRATOR:
        return permissions
    membership = incident.memberships.filter(user=user, is_active=True).first()
    if membership:
        permissions |= permissions_for_role(membership.role)
    else:
        permissions = {
            permission
            for permission in permissions
            if not permission.startswith(("incident.", "period."))
        }
    return permissions


def user_has_permission(user, permission: str, incident=None) -> bool:
    return bool(
        user and user.is_authenticated and permission in permissions_for_user(user, incident)
    )


def has_any_permission(user, permissions: Iterable[str], incident=None) -> bool:
    available = permissions_for_user(user, incident)
    return any(permission in available for permission in permissions)
