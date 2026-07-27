from datetime import datetime, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.authtoken.models import Token

from apps.accounts.models import Role, UserRoleAssignment
from apps.audit.models import AuditEvent
from apps.incidents.models import Incident, IncidentMembership, OperationalPeriod


def user_with_role(username, role=Role.READ_ONLY):
    user = get_user_model().objects.create_user(username, password="safe-test-password")
    UserRoleAssignment.objects.create(user=user, role=role)
    return user


def auth_header(token):
    return {"HTTP_AUTHORIZATION": f"Token {token.key}"}


@pytest.mark.django_db
def test_login_rotates_token_and_returns_a_bounded_lifetime(client, settings):
    settings.ICT_TOKEN_TTL_SECONDS = 3600
    user = user_with_role("rotating-user")

    first = client.post(
        "/api/auth/token/",
        {"username": user.username, "password": "safe-test-password"},
        content_type="application/json",
    )
    assert first.status_code == 200
    first_token = first.json()["token"]
    expires_at = datetime.fromisoformat(first.json()["expires_at"])
    assert timedelta(minutes=59) < expires_at - timezone.now() <= timedelta(hours=1)

    second = client.post(
        "/api/auth/token/",
        {"username": user.username, "password": "safe-test-password"},
        content_type="application/json",
    )
    assert second.status_code == 200
    assert second.json()["token"] != first_token
    assert Token.objects.filter(key=first_token).exists() is False

    login_events = AuditEvent.objects.filter(action="authentication.login").order_by("sequence")
    assert login_events.count() == 2
    assert all("token" not in str(event.details).lower() for event in login_events)


@pytest.mark.django_db
def test_expired_token_is_rejected_without_exposing_another_incident(client, settings):
    settings.ICT_TOKEN_TTL_SECONDS = 60
    user = user_with_role("expired-user")
    token = Token.objects.create(user=user)
    Token.objects.filter(pk=token.pk).update(created=timezone.now() - timedelta(seconds=61))

    response = client.get("/api/incidents/", **auth_header(token))

    assert response.status_code == 401
    assert response.json()["detail"] == "Token has expired."


@pytest.mark.django_db
def test_logout_revokes_current_token_and_records_audit_event(client):
    user = user_with_role("logout-user")
    token = Token.objects.create(user=user)

    response = client.post("/api/auth/logout/", **auth_header(token))

    assert response.status_code == 204
    assert Token.objects.filter(pk=token.pk).exists() is False
    event = AuditEvent.objects.get(action="authentication.logout")
    assert event.actor == user
    assert event.details == {}


@pytest.mark.django_db
def test_incident_scoped_endpoints_hide_unassigned_records(client):
    owner = user_with_role("incident-owner", Role.COML)
    assigned_user = user_with_role("assigned-user", Role.READ_ONLY)
    assigned_incident = Incident.objects.create(
        name="Synthetic Assigned Incident", created_by=owner
    )
    hidden_incident = Incident.objects.create(name="Synthetic Hidden Incident", created_by=owner)
    IncidentMembership.objects.create(
        incident=assigned_incident,
        user=assigned_user,
        role=Role.COMT,
        assigned_by=owner,
    )
    assigned_period = OperationalPeriod.objects.create(
        incident=assigned_incident,
        name="Synthetic Assigned Period",
        starts_at="2026-07-27T08:00:00Z",
        ends_at="2026-07-27T20:00:00Z",
        created_by=owner,
    )
    hidden_period = OperationalPeriod.objects.create(
        incident=hidden_incident,
        name="Synthetic Hidden Period",
        starts_at="2026-07-27T08:00:00Z",
        ends_at="2026-07-27T20:00:00Z",
        created_by=owner,
    )
    headers = auth_header(Token.objects.create(user=assigned_user))

    listed_incidents = client.get("/api/incidents/", **headers)
    listed_periods = client.get("/api/operational-periods/", **headers)

    assert listed_incidents.status_code == 200
    assert [row["id"] for row in listed_incidents.json()["results"]] == [str(assigned_incident.id)]
    assert [row["id"] for row in listed_periods.json()["results"]] == [str(assigned_period.id)]
    assert client.get(f"/api/incidents/{hidden_incident.id}/", **headers).status_code == 404
    assert (
        client.patch(
            f"/api/operational-periods/{hidden_period.id}/",
            {"name": "Synthetic Unauthorized Change"},
            content_type="application/json",
            **headers,
        ).status_code
        == 404
    )
