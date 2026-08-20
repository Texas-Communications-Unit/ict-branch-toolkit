from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.utils import timezone
from rest_framework.authtoken.models import Token

from apps.accounts.models import LocalContingencyAccount, Role, UserRoleAssignment
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
def test_administrator_can_create_activate_revoke_and_disable_local_contingency_account(client):
    admin = user_with_role("contingency-admin", Role.ADMINISTRATOR)
    admin_token = Token.objects.create(user=admin)
    created = client.post(
        "/api/local-contingency-accounts/",
        {
            "username": "synthetic-local-user",
            "display_name": "Synthetic Local User",
            "email": "synthetic-local@example.invalid",
            "role": Role.AUXCOMM,
            "reason": "Synthetic identity-provider outage exercise.",
            "incidents": [],
        },
        content_type="application/json",
        **auth_header(admin_token),
    )
    assert created.status_code == 201, created.content
    temporary_password = created.json()["temporary_password"]
    assert temporary_password
    account = LocalContingencyAccount.objects.get(user__username="synthetic-local-user")
    assert account.must_change_password is True
    assert account.user.toolkit_role.role == Role.AUXCOMM

    blocked = client.post(
        "/api/auth/token/",
        {
            "username": "synthetic-local-user",
            "password": temporary_password,
        },
        content_type="application/json",
    )
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "password_change_required"

    activated = client.post(
        "/api/auth/activate-local/",
        {
            "username": "synthetic-local-user",
            "temporary_password": temporary_password,
            "new_password": "replacement-safe-test-password-2026",
        },
        content_type="application/json",
    )
    assert activated.status_code == 204, activated.content
    signed_in = client.post(
        "/api/auth/token/",
        {
            "username": "synthetic-local-user",
            "password": "replacement-safe-test-password-2026",
        },
        content_type="application/json",
    )
    assert signed_in.status_code == 200
    assert Token.objects.filter(user=account.user).exists()

    revoked = client.post(
        "/api/local-contingency-accounts/synthetic-local-user/sign-out-all/",
        **auth_header(admin_token),
    )
    assert revoked.status_code == 204
    assert Token.objects.filter(user=account.user).exists() is False

    disabled = client.post(
        "/api/local-contingency-accounts/synthetic-local-user/disable/",
        {"reason": "Synthetic exercise complete."},
        content_type="application/json",
        **auth_header(admin_token),
    )
    assert disabled.status_code == 200, disabled.content
    account.user.refresh_from_db()
    assert account.user.is_active is False
    assert temporary_password not in str(AuditEvent.objects.values_list("details", flat=True))


@pytest.mark.django_db
def test_password_reset_email_is_generic_single_use_and_revokes_sessions(client, settings):
    settings.ICT_EMAIL_ENABLED = True
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.ICT_PUBLIC_BASE_URL = "https://toolkit.example.invalid"
    admin = user_with_role("reset-admin", Role.ADMINISTRATOR)
    admin_token = Token.objects.create(user=admin)
    created = client.post(
        "/api/local-contingency-accounts/",
        {
            "username": "reset-user",
            "display_name": "Reset User",
            "email": "reset-user@example.invalid",
            "role": Role.READ_ONLY,
            "reason": "Synthetic reset workflow test.",
            "incidents": [],
        },
        content_type="application/json",
        **auth_header(admin_token),
    )
    assert created.status_code == 201, created.content

    unknown = client.post(
        "/api/auth/password-reset/request/",
        {"email": "unknown@example.invalid"},
        content_type="application/json",
    )
    assert unknown.status_code == 204
    assert len(mail.outbox) == 0

    requested = client.post(
        "/api/auth/password-reset/request/",
        {"email": "RESET-USER@example.invalid"},
        content_type="application/json",
    )
    assert requested.status_code == 204
    assert len(mail.outbox) == 1
    assert "reset-user" in mail.outbox[0].body
    reset_url = next(
        line for line in mail.outbox[0].body.splitlines() if line.startswith("https://")
    )
    query = parse_qs(urlparse(reset_url).query)

    reset_user = get_user_model().objects.get(username="reset-user")
    Token.objects.create(user=reset_user)
    confirmed = client.post(
        "/api/auth/password-reset/confirm/",
        {
            "uid": query["reset_uid"][0],
            "token": query["reset_token"][0],
            "new_password": "replacement-safe-test-password-2026",
        },
        content_type="application/json",
    )
    assert confirmed.status_code == 204, confirmed.content
    assert Token.objects.filter(user=reset_user).exists() is False
    assert reset_user.local_contingency_account.must_change_password is False

    reused = client.post(
        "/api/auth/password-reset/confirm/",
        {
            "uid": query["reset_uid"][0],
            "token": query["reset_token"][0],
            "new_password": "another-safe-test-password-2026",
        },
        content_type="application/json",
    )
    assert reused.status_code == 400

    admin_sent = client.post(
        "/api/local-contingency-accounts/reset-user/send-password-reset/",
        **auth_header(admin_token),
    )
    assert admin_sent.status_code == 204, admin_sent.content
    assert len(mail.outbox) == 2
    assert AuditEvent.objects.filter(
        action="local_contingency_account.password_reset_sent"
    ).exists()

    email_updated = client.post(
        "/api/local-contingency-accounts/reset-user/set-email/",
        {"email": "updated-reset-user@example.invalid"},
        content_type="application/json",
        **auth_header(admin_token),
    )
    assert email_updated.status_code == 200, email_updated.content
    assert email_updated.json()["email"] == "updated-reset-user@example.invalid"
    assert AuditEvent.objects.filter(action="local_contingency_account.email_updated").exists()


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
