from collections.abc import Mapping

from django.conf import settings
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import Role
from apps.accounts.policy import role_for_user

from .models import RESTRICTED_ASSIGNMENT_FIELDS, SensitiveFieldRule

RESTRICTED_VALUE = "Access restricted"


def _request_policy_cache(request) -> dict:
    if request is None:
        return {}
    cache = getattr(request, "_ict_sensitive_field_policy_cache", None)
    if cache is None:
        cache = {}
        request._ict_sensitive_field_policy_cache = cache
    return cache


def effective_incident_role(user, incident, *, request=None) -> str:
    cache = _request_policy_cache(request)
    cache_key = ("role", incident.pk, user.pk)
    if cache_key in cache:
        return cache[cache_key]
    global_role = role_for_user(user)
    if global_role == Role.ADMINISTRATOR:
        cache[cache_key] = global_role
        return cache[cache_key]
    prefetched_memberships = getattr(user, "active_presence_memberships", None)
    if prefetched_memberships is None:
        membership = incident.memberships.filter(user=user, is_active=True).first()
    else:
        membership = prefetched_memberships[0] if prefetched_memberships else None
    cache[cache_key] = membership.role if membership else global_role
    return cache[cache_key]


def _rules_by_field(incident, *, request=None) -> dict[str, SensitiveFieldRule]:
    cache = _request_policy_cache(request)
    cache_key = ("rules", incident.pk)
    if cache_key not in cache:
        cache[cache_key] = {
            rule.field_name: rule
            for rule in incident.sensitive_field_rules.filter(resource_type="plan_assignment")
        }
    return cache[cache_key]


def _roles_for(rule: SensitiveFieldRule | None, action: str) -> set[str]:
    if rule:
        configured = rule.edit_roles if action == "edit" else rule.view_roles
    elif action == "edit":
        configured = settings.ICT_RESTRICTED_FIELD_DEFAULT_EDIT_ROLES
    else:
        configured = settings.ICT_RESTRICTED_FIELD_DEFAULT_VIEW_ROLES
    return set(configured)


def enforce_assignment_field_edits(*, user, incident, fields: Mapping, request=None) -> None:
    role = effective_incident_role(user, incident, request=request)
    rules = _rules_by_field(incident, request=request)
    denied = [
        field
        for field in RESTRICTED_ASSIGNMENT_FIELDS
        if field in fields and role not in _roles_for(rules.get(field), "edit")
    ]
    if denied:
        raise PermissionDenied(
            {field: "Your incident role cannot edit this restricted field." for field in denied}
        )


def filter_assignment_snapshot(*, user, incident, snapshot: Mapping, request=None) -> dict:
    filtered = dict(snapshot)
    role = effective_incident_role(user, incident, request=request)
    rules = _rules_by_field(incident, request=request)
    for field in RESTRICTED_ASSIGNMENT_FIELDS:
        if field not in filtered:
            continue
        rule = rules.get(field)
        if role in _roles_for(rule, "view"):
            continue
        visibility = rule.unauthorized_visibility if rule else SensitiveFieldRule.Visibility.OMITTED
        if visibility == SensitiveFieldRule.Visibility.RESTRICTED:
            filtered[field] = RESTRICTED_VALUE
        else:
            filtered.pop(field, None)
    return filtered
