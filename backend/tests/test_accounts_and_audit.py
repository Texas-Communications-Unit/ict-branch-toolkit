import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from rest_framework.authtoken.models import Token

from apps.accounts.identity import LocalIdentityProvider, configured_identity_provider
from apps.accounts.models import Role, UserRoleAssignment
from apps.audit.models import AuditEvent
from apps.incidents.models import Incident, IncidentMembership


def auth_header(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {"HTTP_AUTHORIZATION": f"Token {token.key}"}


def user_with_role(username, role):
    user = get_user_model().objects.create_user(username, password="safe-test-password")
    UserRoleAssignment.objects.create(user=user, role=role)
    return user


@pytest.mark.django_db
def test_current_user_returns_central_policy_capabilities(client):
    coml = user_with_role("coml", Role.COML)
    response = client.get("/api/me/", **auth_header(coml))
    assert response.status_code == 200
    assert response.json()["role"] == Role.COML
    assert "incident.create" in response.json()["permissions"]
    assert "library.import" not in response.json()["permissions"]


@pytest.mark.django_db
@override_settings(ICT_ROLE_POLICY_OVERRIDES={Role.READ_ONLY: ["incident.create"]})
def test_role_policy_can_be_replaced_from_configuration(client):
    reader = user_with_role("configured-reader", Role.READ_ONLY)
    response = client.get("/api/me/", **auth_header(reader))
    assert response.json()["permissions"] == ["incident.create"]


def test_external_identity_provider_fails_closed_until_implemented(settings):
    assert isinstance(configured_identity_provider(), LocalIdentityProvider)
    settings.ICT_IDENTITY_PROVIDER = "civicrm"
    with pytest.raises(ImproperlyConfigured, match="Only the local identity provider"):
        configured_identity_provider()


@pytest.mark.django_db
def test_incident_membership_scopes_access_and_change_policy(client):
    coml = user_with_role("coml", Role.COML)
    technician = user_with_role("technician", Role.READ_ONLY)
    outsider = user_with_role("outsider", Role.READ_ONLY)

    created = client.post(
        "/api/incidents/",
        {"name": "Synthetic Communications Exercise"},
        content_type="application/json",
        **auth_header(coml),
    )
    assert created.status_code == 201
    incident = Incident.objects.get()
    assert IncidentMembership.objects.filter(incident=incident, user=coml).exists()

    membership = client.post(
        "/api/incident-memberships/",
        {"incident": str(incident.id), "user": technician.id, "role": Role.COMT},
        content_type="application/json",
        **auth_header(coml),
    )
    assert membership.status_code == 201

    response = client.patch(
        f"/api/incidents/{incident.id}/",
        {"status": "active"},
        content_type="application/json",
        **auth_header(technician),
    )
    assert response.status_code == 200
    period = client.post(
        "/api/operational-periods/",
        {
            "incident": str(incident.id),
            "name": "Synthetic Operational Period",
            "starts_at": "2026-07-22T08:00:00Z",
            "ends_at": "2026-07-22T20:00:00Z",
        },
        content_type="application/json",
        **auth_header(technician),
    )
    assert period.status_code == 201
    assert client.get("/api/incidents/", **auth_header(outsider)).json()["count"] == 0


@pytest.mark.django_db
def test_archive_replaces_delete_and_records_append_only_audit(client):
    admin = get_user_model().objects.create_superuser("admin", password="safe-test-password")
    incident = Incident.objects.create(name="Synthetic Archive Exercise", created_by=admin)
    IncidentMembership.objects.create(
        incident=incident,
        user=admin,
        role=Role.ADMINISTRATOR,
        assigned_by=admin,
    )
    headers = auth_header(admin)

    assert client.delete(f"/api/incidents/{incident.id}/", **headers).status_code == 405
    archived = client.post(f"/api/incidents/{incident.id}/archive/", **headers)
    assert archived.status_code == 200
    assert archived.json()["archived_at"]
    assert client.get("/api/incidents/", **headers).json()["count"] == 0

    event = AuditEvent.objects.get(action="incident.archived")
    with pytest.raises(RuntimeError, match="append-only"):
        event.delete()
    with pytest.raises(RuntimeError, match="append-only"):
        AuditEvent.objects.filter(pk=event.pk).update(action="changed")
