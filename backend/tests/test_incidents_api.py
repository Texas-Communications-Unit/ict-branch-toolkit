import pytest
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token

from apps.accounts.models import Role
from apps.audit.models import AuditEvent
from apps.incidents.models import Incident, IncidentMembership, OperationalPeriod


def auth_header(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {"HTTP_AUTHORIZATION": f"Token {token.key}"}


def add_incident_member(incident, user, role, assigned_by):
    return IncidentMembership.objects.create(
        incident=incident,
        user=user,
        role=role,
        assigned_by=assigned_by,
    )


@pytest.mark.django_db
def test_anonymous_user_cannot_list_incidents(client):
    response = client.get("/api/incidents/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_authenticated_reader_can_list_but_not_create(client):
    user = get_user_model().objects.create_user("reader", password="safe-test-password")
    response = client.get("/api/incidents/", **auth_header(user))
    assert response.status_code == 200
    response = client.post("/api/incidents/", {"name": "Synthetic Incident"}, **auth_header(user))
    assert response.status_code == 403


@pytest.mark.django_db
def test_administrator_creates_incident_and_operational_period(client):
    admin = get_user_model().objects.create_superuser(
        "admin", "admin@example.invalid", "safe-test-password"
    )
    headers = auth_header(admin)
    incident_response = client.post(
        "/api/incidents/",
        {"name": "Synthetic Flood Exercise", "incident_number": "SYN-001"},
        content_type="application/json",
        **headers,
    )
    assert incident_response.status_code == 201
    incident_id = incident_response.json()["id"]

    period_response = client.post(
        "/api/operational-periods/",
        {
            "incident": incident_id,
            "name": "Operational Period 1",
            "starts_at": "2026-01-01T08:00:00Z",
            "ends_at": "2026-01-01T20:00:00Z",
        },
        content_type="application/json",
        **headers,
    )
    assert period_response.status_code == 201
    assert Incident.objects.count() == 1
    assert OperationalPeriod.objects.count() == 1


@pytest.mark.django_db
def test_operational_period_requires_end_after_start(client):
    admin = get_user_model().objects.create_superuser("admin", password="safe-test-password")
    incident = Incident.objects.create(name="Synthetic Incident", created_by=admin)
    response = client.post(
        "/api/operational-periods/",
        {
            "incident": str(incident.id),
            "name": "Invalid Period",
            "starts_at": "2026-01-01T20:00:00Z",
            "ends_at": "2026-01-01T08:00:00Z",
        },
        content_type="application/json",
        **auth_header(admin),
    )
    assert response.status_code == 400
    assert "ends_at" in response.json()


@pytest.mark.django_db
def test_authorized_incident_name_update_preserves_identity_and_audits_values(client):
    admin = get_user_model().objects.create_superuser("edit-admin", password="safe-test-password")
    incident = Incident.objects.create(
        name="Synthetic Incdent",
        incident_number="SYN-EDIT-1",
        created_by=admin,
    )

    response = client.patch(
        f"/api/incidents/{incident.id}/",
        {"name": "  Synthetic Incident  "},
        content_type="application/json",
        **auth_header(admin),
    )

    assert response.status_code == 200, response.content
    assert response.json()["id"] == str(incident.id)
    assert response.json()["name"] == "Synthetic Incident"
    incident.refresh_from_db()
    assert incident.id == response.json()["id"] or str(incident.id) == response.json()["id"]
    assert incident.incident_number == "SYN-EDIT-1"

    event = AuditEvent.objects.get(action="incident.updated", target_id=str(incident.id))
    assert event.actor == admin
    assert event.details["incident_id"] == str(incident.id)
    assert event.details["changed_fields"] == ["name"]
    assert event.details["before"] == {"name": "Synthetic Incdent"}
    assert event.details["after"] == {"name": "Synthetic Incident"}


@pytest.mark.django_db
def test_authorized_operational_period_update_preserves_scope_and_audits_values(client):
    admin = get_user_model().objects.create_superuser("period-admin", password="safe-test-password")
    incident = Incident.objects.create(name="Synthetic Incident", created_by=admin)
    period = OperationalPeriod.objects.create(
        incident=incident,
        name="Operational Period One",
        starts_at="2026-01-01T08:00:00Z",
        ends_at="2026-01-01T20:00:00Z",
        created_by=admin,
    )

    response = client.patch(
        f"/api/operational-periods/{period.id}/",
        {
            "name": "Operational Period 1",
            "starts_at": "2026-01-01T09:00:00Z",
            "ends_at": "2026-01-01T21:00:00Z",
        },
        content_type="application/json",
        **auth_header(admin),
    )

    assert response.status_code == 200, response.content
    assert response.json()["id"] == str(period.id)
    assert response.json()["incident"] == str(incident.id)
    period.refresh_from_db()
    assert period.incident_id == incident.id

    event = AuditEvent.objects.get(
        action="operational_period.updated", target_id=str(period.id)
    )
    assert event.actor == admin
    assert event.details["incident_id"] == str(incident.id)
    assert event.details["changed_fields"] == ["ends_at", "name", "starts_at"]
    assert event.details["before"]["name"] == "Operational Period One"
    assert event.details["after"]["name"] == "Operational Period 1"


@pytest.mark.django_db
def test_read_only_incident_member_cannot_edit_incident_or_period(client):
    admin = get_user_model().objects.create_superuser("scope-admin", password="safe-test-password")
    reader = get_user_model().objects.create_user("scope-reader", password="safe-test-password")
    incident = Incident.objects.create(name="Synthetic Incident", created_by=admin)
    add_incident_member(incident, reader, Role.READ_ONLY, admin)
    period = OperationalPeriod.objects.create(
        incident=incident,
        name="Operational Period 1",
        starts_at="2026-01-01T08:00:00Z",
        ends_at="2026-01-01T20:00:00Z",
        created_by=admin,
    )
    headers = auth_header(reader)

    incident_response = client.patch(
        f"/api/incidents/{incident.id}/",
        {"name": "Unauthorized Rename"},
        content_type="application/json",
        **headers,
    )
    period_response = client.patch(
        f"/api/operational-periods/{period.id}/",
        {"name": "Unauthorized Period"},
        content_type="application/json",
        **headers,
    )

    assert incident_response.status_code == 403
    assert period_response.status_code == 403
    incident.refresh_from_db()
    period.refresh_from_db()
    assert incident.name == "Synthetic Incident"
    assert period.name == "Operational Period 1"
    assert not AuditEvent.objects.filter(action__in=["incident.updated", "operational_period.updated"]).exists()


@pytest.mark.django_db
def test_incident_update_rejects_blank_and_immutable_fields_without_audit(client):
    admin = get_user_model().objects.create_superuser("validation-admin", password="safe-test-password")
    incident = Incident.objects.create(
        name="Synthetic Incident",
        incident_number="SYN-IMMUTABLE",
        created_by=admin,
    )
    headers = auth_header(admin)

    blank = client.patch(
        f"/api/incidents/{incident.id}/",
        {"name": "   "},
        content_type="application/json",
        **headers,
    )
    immutable = client.patch(
        f"/api/incidents/{incident.id}/",
        {"incident_number": "CHANGED", "status": "closed"},
        content_type="application/json",
        **headers,
    )

    assert blank.status_code == 400
    assert "name" in blank.json()
    assert immutable.status_code == 400
    assert "incident_number" in immutable.json()
    assert "status" in immutable.json()
    incident.refresh_from_db()
    assert incident.name == "Synthetic Incident"
    assert incident.incident_number == "SYN-IMMUTABLE"
    assert incident.status == Incident.Status.PLANNING
    assert not AuditEvent.objects.filter(action="incident.updated").exists()


@pytest.mark.django_db
def test_operational_period_update_rejects_invalid_time_and_cross_incident_move(client):
    admin = get_user_model().objects.create_superuser("period-validation", password="safe-test-password")
    incident = Incident.objects.create(name="Synthetic Incident A", created_by=admin)
    other_incident = Incident.objects.create(name="Synthetic Incident B", created_by=admin)
    period = OperationalPeriod.objects.create(
        incident=incident,
        name="Operational Period 1",
        starts_at="2026-01-01T08:00:00Z",
        ends_at="2026-01-01T20:00:00Z",
        created_by=admin,
    )
    headers = auth_header(admin)

    bad_time = client.patch(
        f"/api/operational-periods/{period.id}/",
        {"ends_at": "2026-01-01T07:00:00Z"},
        content_type="application/json",
        **headers,
    )
    cross_incident = client.patch(
        f"/api/operational-periods/{period.id}/",
        {"incident": str(other_incident.id)},
        content_type="application/json",
        **headers,
    )

    assert bad_time.status_code == 400
    assert "ends_at" in bad_time.json()
    assert cross_incident.status_code == 400
    assert "incident" in cross_incident.json()
    period.refresh_from_db()
    assert period.incident_id == incident.id
    assert not AuditEvent.objects.filter(action="operational_period.updated").exists()
