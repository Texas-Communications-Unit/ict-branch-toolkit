import hashlib

import pytest
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token

from apps.accounts.models import Role, UserRoleAssignment
from apps.incidents.models import Incident, IncidentMembership, OperationalPeriod
from apps.plans.models import Assignment, ICS205Plan, PlanRevision
from apps.sites.models import RadioSite, SiteAssignment


def auth_header(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {"HTTP_AUTHORIZATION": f"Token {token.key}"}


def setup_scenario():
    admin = get_user_model().objects.create_superuser(
        "verify-admin", "verify-admin@example.invalid", "safe-test-password"
    )
    incident = Incident.objects.create(
        name="Synthetic Verification Exercise",
        incident_number="SYN-VERIFY",
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
        name="Synthetic Verification Site",
        latitude="33.214500",
        longitude="-97.133100",
        created_by=admin,
    )
    SiteAssignment.objects.create(site=site, assignment=assignment)
    return admin, incident, revision


@pytest.mark.django_db
def test_verify_pdf_export_matches_recorded_digest(client):
    admin, _, revision = setup_scenario()
    headers = auth_header(admin)
    assert client.post(f"/api/plan-revisions/{revision.id}/approve/", **headers).status_code == 200

    export_response = client.get(f"/api/plan-revisions/{revision.id}/pdf/", **headers)
    assert export_response.status_code == 200
    digest = hashlib.sha256(export_response.content).hexdigest()

    verify_response = client.post(
        f"/api/audit/revisions/{revision.id}/exports/pdf/verify/",
        {"content_sha256": digest},
        content_type="application/json",
        **headers,
    )
    assert verify_response.status_code == 200
    body = verify_response.json()
    assert body["verified"] is True
    assert body["revision_number"] == revision.number
    assert body["action"] == "plan_revision.pdf_exported"


@pytest.mark.django_db
def test_verify_spatial_export_matches_recorded_digest(client):
    admin, _, revision = setup_scenario()
    headers = auth_header(admin)
    assert client.post(f"/api/plan-revisions/{revision.id}/approve/", **headers).status_code == 200

    export_response = client.get(f"/api/spatial-exports/{revision.id}/geojson/", **headers)
    assert export_response.status_code == 200
    digest = hashlib.sha256(export_response.content).hexdigest()

    verify_response = client.post(
        f"/api/audit/revisions/{revision.id}/exports/geojson/verify/",
        {"content_sha256": digest},
        content_type="application/json",
        **headers,
    )
    assert verify_response.status_code == 200
    assert verify_response.json()["verified"] is True


@pytest.mark.django_db
def test_verify_reports_no_match_for_a_wrong_digest(client):
    admin, _, revision = setup_scenario()
    headers = auth_header(admin)
    assert client.post(f"/api/plan-revisions/{revision.id}/approve/", **headers).status_code == 200
    assert client.get(f"/api/plan-revisions/{revision.id}/pdf/", **headers).status_code == 200

    wrong_digest = hashlib.sha256(b"not the exported file").hexdigest()
    verify_response = client.post(
        f"/api/audit/revisions/{revision.id}/exports/pdf/verify/",
        {"content_sha256": wrong_digest},
        content_type="application/json",
        **headers,
    )
    assert verify_response.status_code == 200
    assert verify_response.json()["verified"] is False


@pytest.mark.django_db
def test_verify_accepts_an_uploaded_file_instead_of_a_precomputed_digest(client):
    admin, _, revision = setup_scenario()
    headers = auth_header(admin)
    assert client.post(f"/api/plan-revisions/{revision.id}/approve/", **headers).status_code == 200
    export_response = client.get(f"/api/plan-revisions/{revision.id}/pdf/", **headers)

    from django.core.files.uploadedfile import SimpleUploadedFile

    upload = SimpleUploadedFile(
        "revision.pdf", export_response.content, content_type="application/pdf"
    )
    verify_response = client.post(
        f"/api/audit/revisions/{revision.id}/exports/pdf/verify/",
        {"file": upload},
        **headers,
    )
    assert verify_response.status_code == 200
    assert verify_response.json()["verified"] is True


@pytest.mark.django_db
def test_verify_rejects_role_without_export_permission(client):
    admin, incident, revision = setup_scenario()
    headers = auth_header(admin)
    assert client.post(f"/api/plan-revisions/{revision.id}/approve/", **headers).status_code == 200
    export_response = client.get(f"/api/plan-revisions/{revision.id}/pdf/", **headers)
    digest = hashlib.sha256(export_response.content).hexdigest()

    reader = get_user_model().objects.create_user("verify-reader", password="safe-test-password")
    UserRoleAssignment.objects.create(user=reader, role=Role.READ_ONLY)
    IncidentMembership.objects.create(
        incident=incident, user=reader, role=Role.READ_ONLY, assigned_by=admin
    )
    reader_headers = auth_header(reader)

    verify_response = client.post(
        f"/api/audit/revisions/{revision.id}/exports/pdf/verify/",
        {"content_sha256": digest},
        content_type="application/json",
        **reader_headers,
    )
    assert verify_response.status_code == 403


@pytest.mark.django_db
def test_verify_rejects_unknown_export_format(client):
    admin, _, revision = setup_scenario()
    headers = auth_header(admin)
    response = client.post(
        f"/api/audit/revisions/{revision.id}/exports/svg/verify/",
        {"content_sha256": "0" * 64},
        content_type="application/json",
        **headers,
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_verify_requires_a_digest_or_file(client):
    admin, _, revision = setup_scenario()
    headers = auth_header(admin)
    response = client.post(
        f"/api/audit/revisions/{revision.id}/exports/pdf/verify/",
        {},
        content_type="application/json",
        **headers,
    )
    assert response.status_code == 400
