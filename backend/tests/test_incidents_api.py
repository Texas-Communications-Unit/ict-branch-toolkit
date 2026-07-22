import pytest
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token

from apps.incidents.models import Incident, OperationalPeriod


def auth_header(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {"HTTP_AUTHORIZATION": f"Token {token.key}"}


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
