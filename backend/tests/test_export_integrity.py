import hashlib
import json

import pytest
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token

from apps.accounts.models import Role, UserRoleAssignment
from apps.audit.models import AuditEvent
from apps.incidents.models import Incident, IncidentMembership, OperationalPeriod
from apps.plans.models import Assignment, ICS205Plan, PlanRevision
from apps.sites.models import RadioSite, SiteAssignment


def auth_header(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {"HTTP_AUTHORIZATION": f"Token {token.key}"}


def setup_scenario():
    admin = get_user_model().objects.create_superuser(
        "export-admin", "export-admin@example.invalid", "safe-test-password"
    )
    incident = Incident.objects.create(
        name="Synthetic Export Integrity Exercise",
        incident_number="SYN-EXP",
        created_by=admin,
    )
    IncidentMembership.objects.create(
        incident=incident, user=admin, role=Role.ADMINISTRATOR, assigned_by=admin
    )
    period = OperationalPeriod.objects.create(
        incident=incident,
        name="Operational Period 1",
        starts_at="2026-07-23T08:00:00Z",
        ends_at="2026-07-23T20:00:00Z",
        created_by=admin,
    )
    plan = ICS205Plan.objects.create(incident=incident, operational_period=period, created_by=admin)
    revision = PlanRevision.objects.create(plan=plan, number=1, created_by=admin)
    assignment = Assignment.objects.create(
        revision=revision,
        position=1,
        function="Command",
        channel_name="SYN CALL",
        assignment="Synthetic exercise",
        rx_frequency_hz=155_001_000,
        tx_frequency_hz=155_001_000,
        resource_snapshot={"type": "incident", "name": "SYN CALL"},
    )
    site = RadioSite.objects.create(
        incident=incident,
        name="Synthetic Export Site",
        latitude="33.214500",
        longitude="-97.133100",
        created_by=admin,
    )
    SiteAssignment.objects.create(site=site, assignment=assignment)
    return admin, incident, revision


@pytest.mark.django_db
def test_pdf_export_records_content_digest_matching_returned_bytes(client):
    admin, _, revision = setup_scenario()
    headers = auth_header(admin)
    assert client.post(f"/api/plan-revisions/{revision.id}/approve/", **headers).status_code == 200

    response = client.get(f"/api/plan-revisions/{revision.id}/pdf/", **headers)
    assert response.status_code == 200

    event = AuditEvent.objects.filter(action="plan_revision.pdf_exported").latest("occurred_at")
    assert event.details["format"] == "pdf"
    assert event.details["revision_number"] == revision.number
    assert event.details["revision_status"] == PlanRevision.Status.APPROVED
    assert event.details["content_sha256"] == hashlib.sha256(response.content).hexdigest()
    assert event.details["byte_size"] == len(response.content)


@pytest.mark.parametrize(
    "export_format",
    ["geojson", "csv", "kml", "map"],
)
@pytest.mark.django_db
def test_spatial_export_records_content_digest_and_approval_stamp(client, export_format):
    admin, _, revision = setup_scenario()
    headers = auth_header(admin)
    assert client.post(f"/api/plan-revisions/{revision.id}/approve/", **headers).status_code == 200
    revision.refresh_from_db()

    response = client.get(f"/api/spatial-exports/{revision.id}/{export_format}/", **headers)
    assert response.status_code == 200

    event = AuditEvent.objects.filter(action=f"site_export.{export_format}").latest("occurred_at")
    assert event.details["content_sha256"] == hashlib.sha256(response.content).hexdigest()
    assert event.details["revision_status"] == PlanRevision.Status.APPROVED
    assert event.details["filename"]

    body = response.content.decode()
    approved_at = revision.approved_at.isoformat()
    if export_format == "geojson":
        payload = json.loads(body)
        assert payload["approval_status"] == "approved"
        assert payload["approved_at"] == approved_at
        assert payload["app_version"]
    else:
        assert "approved" in body.lower()
        assert approved_at in body


@pytest.mark.django_db
def test_spatial_export_rejects_draft_revision_before_recording_any_export(client):
    admin, _, revision = setup_scenario()
    headers = auth_header(admin)
    response = client.get(f"/api/spatial-exports/{revision.id}/geojson/", **headers)
    assert response.status_code == 400
    assert not AuditEvent.objects.filter(action="site_export.geojson").exists()


@pytest.mark.django_db
def test_export_denied_for_role_without_export_permission(client):
    admin, incident, revision = setup_scenario()
    headers = auth_header(admin)
    assert client.post(f"/api/plan-revisions/{revision.id}/approve/", **headers).status_code == 200

    reader = get_user_model().objects.create_user("export-reader", password="safe-test-password")
    UserRoleAssignment.objects.create(user=reader, role=Role.READ_ONLY)
    IncidentMembership.objects.create(
        incident=incident, user=reader, role=Role.READ_ONLY, assigned_by=admin
    )
    reader_headers = auth_header(reader)

    pdf_response = client.get(f"/api/plan-revisions/{revision.id}/pdf/", **reader_headers)
    assert pdf_response.status_code == 403
    geojson_response = client.get(f"/api/spatial-exports/{revision.id}/geojson/", **reader_headers)
    assert geojson_response.status_code == 403
    assert not AuditEvent.objects.filter(action="plan_revision.pdf_exported").exists()
    assert not AuditEvent.objects.filter(action="site_export.geojson").exists()


@pytest.mark.django_db
def test_copying_an_approved_revision_does_not_change_its_recorded_export_digest(client):
    admin, _, revision = setup_scenario()
    headers = auth_header(admin)
    assert client.post(f"/api/plan-revisions/{revision.id}/approve/", **headers).status_code == 200

    original = client.get(f"/api/plan-revisions/{revision.id}/pdf/", **headers)
    original_digest = hashlib.sha256(original.content).hexdigest()

    copied = client.post(f"/api/plan-revisions/{revision.id}/copy/", **headers)
    assert copied.status_code == 201, copied.content
    draft = PlanRevision.objects.get(pk=copied.json()["id"])
    draft_assignment = draft.assignments.get()
    changed = client.patch(
        f"/api/plan-assignments/{draft_assignment.id}/",
        {"remarks": "Concurrent draft change made after original export"},
        content_type="application/json",
        **headers,
    )
    assert changed.status_code == 200

    replay = client.get(f"/api/plan-revisions/{revision.id}/pdf/", **headers)
    assert hashlib.sha256(replay.content).hexdigest() == original_digest
    assert replay.content == original.content


@pytest.mark.django_db
def test_tampered_download_is_detected_against_the_recorded_digest(client):
    admin, _, revision = setup_scenario()
    headers = auth_header(admin)
    assert client.post(f"/api/plan-revisions/{revision.id}/approve/", **headers).status_code == 200

    response = client.get(f"/api/plan-revisions/{revision.id}/pdf/", **headers)
    event = AuditEvent.objects.filter(action="plan_revision.pdf_exported").latest("occurred_at")

    tampered = response.content + b"tampered"
    assert hashlib.sha256(tampered).hexdigest() != event.details["content_sha256"]
    assert hashlib.sha256(response.content).hexdigest() == event.details["content_sha256"]
