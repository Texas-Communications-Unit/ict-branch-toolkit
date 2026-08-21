import json
from hashlib import sha256
from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from pypdf import PdfReader
from rest_framework.authtoken.models import Token

from apps.accounts.models import Role, UserRoleAssignment
from apps.audit.models import AuditEvent
from apps.incidents.models import Incident, IncidentMembership, OperationalPeriod
from apps.plans.models import Assignment, AssignmentRelationship, ICS205Plan, PlanRevision
from apps.plans.pdf import FORM_SHA256, FORM_TEMPLATE, render_ics205


def assert_flattened_pdf(reader):
    assert not reader.get_fields()
    for page in reader.pages:
        annotations = page.get("/Annots", [])
        assert all(
            annotation.get_object().get("/Subtype") != "/Widget" for annotation in annotations
        )


def auth_header(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {"HTTP_AUTHORIZATION": f"Token {token.key}"}


def setup_incident():
    admin = get_user_model().objects.create_superuser(
        "plan-admin", "plan-admin@example.invalid", "safe-test-password"
    )
    incident = Incident.objects.create(
        name="Synthetic Tornado Exercise", incident_number="SYN-205", created_by=admin
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
    return admin, incident, period


def create_plan(client, admin, incident, period):
    response = client.post(
        "/api/ics205-plans/",
        {
            "incident": str(incident.id),
            "operational_period": str(period.id),
            "title": "Synthetic ICS-205",
        },
        content_type="application/json",
        **auth_header(admin),
    )
    assert response.status_code == 201, response.content
    plan = ICS205Plan.objects.get()
    return plan, plan.revisions.get()


def add_assignment(client, admin, revision, position, name):
    response = client.post(
        "/api/plan-assignments/",
        {
            "revision": str(revision.id),
            "position": position,
            "function": "Command",
            "channel_name": name,
            "assignment": "Synthetic exercise",
            "operating_classification": "fixed_pair",
            "rx_frequency_hz": 155000000 + position * 1000,
            "tx_frequency_hz": 155000000 + position * 1000,
            "mode": "Analog FM",
            "structured_note": "patch" if position == 1 else "",
            "remarks": "Synthetic data only",
            "contact_name": "Private Synthetic Contact",
        },
        content_type="application/json",
        **auth_header(admin),
    )
    assert response.status_code == 201, response.content
    return Assignment.objects.get(pk=response.json()["id"])


@pytest.mark.django_db
def test_plan_approval_locks_children_and_copy_forward_preserves_history(client):
    admin, incident, period = setup_incident()
    plan, revision = create_plan(client, admin, incident, period)
    first = add_assignment(client, admin, revision, 1, "SYN CALL")
    second = add_assignment(client, admin, revision, 2, "SYN TAC")

    relationship = client.post(
        "/api/plan-relationships/",
        {
            "revision": str(revision.id),
            "relationship_type": "patch",
            "label": "Synthetic patch",
            "assignments": [str(first.id), str(second.id)],
        },
        content_type="application/json",
        **auth_header(admin),
    )
    assert relationship.status_code == 201, relationship.content

    approved = client.post(f"/api/plan-revisions/{revision.id}/approve/", **auth_header(admin))
    assert approved.status_code == 200
    revision.refresh_from_db()
    assert revision.is_locked
    assert revision.approved_by == admin

    changed = client.patch(
        f"/api/plan-assignments/{first.id}/",
        {"remarks": "Forbidden change"},
        content_type="application/json",
        **auth_header(admin),
    )
    assert changed.status_code == 400
    deleted = client.delete(f"/api/plan-assignments/{first.id}/", **auth_header(admin))
    assert deleted.status_code == 400

    copied = client.post(f"/api/plan-revisions/{revision.id}/copy/", **auth_header(admin))
    assert copied.status_code == 201, copied.content
    draft = PlanRevision.objects.get(pk=copied.json()["id"])
    assert draft.number == 2
    assert draft.status == PlanRevision.Status.DRAFT
    assert draft.assignments.count() == 2
    assert draft.relationships.get().assignments.count() == 2

    draft_first = draft.assignments.get(position=1)
    changed = client.patch(
        f"/api/plan-assignments/{draft_first.id}/",
        {
            "remarks": "New draft change",
            "operating_classification": "transmit_only",
            "rx_frequency_hz": None,
            "rx_squelch": "",
            "tx_squelch": "NAC 293",
        },
        content_type="application/json",
        **auth_header(admin),
    )
    assert changed.status_code == 200
    comparison = client.get(
        f"/api/plan-revisions/{revision.id}/compare/?other={draft.id}",
        **auth_header(admin),
    )
    assert comparison.status_code == 200
    changed_fields = comparison.json()["changes"][0]["changed_fields"]
    assert {
        "operating_classification",
        "rx_frequency_hz",
        "tx_squelch",
        "remarks",
    } <= set(changed_fields)
    first.refresh_from_db()
    assert first.remarks == "Synthetic data only"
    assert plan.revisions.count() == 2


@pytest.mark.django_db
def test_patch_relationship_requires_two_rows_from_same_revision(client):
    admin, incident, period = setup_incident()
    _, revision = create_plan(client, admin, incident, period)
    first = add_assignment(client, admin, revision, 1, "SYN CALL")

    invalid = client.post(
        "/api/plan-relationships/",
        {
            "revision": str(revision.id),
            "relationship_type": "patch",
            "assignments": [str(first.id)],
        },
        content_type="application/json",
        **auth_header(admin),
    )
    assert invalid.status_code == 400
    assert AssignmentRelationship.objects.count() == 0


@pytest.mark.django_db
def test_operating_classification_requires_explicit_consistent_intent(client):
    admin, incident, period = setup_incident()
    _, revision = create_plan(client, admin, incident, period)
    base = {
        "revision": str(revision.id),
        "position": 1,
        "function": "Alerting",
        "channel_name": "SYN BROADCAST",
        "tx_frequency_hz": 155_000_000,
    }

    missing_classification = client.post(
        "/api/plan-assignments/",
        base,
        content_type="application/json",
        **auth_header(admin),
    )
    assert missing_classification.status_code == 400
    assert "operating_classification" in missing_classification.json()

    inconsistent = client.post(
        "/api/plan-assignments/",
        {**base, "operating_classification": "receive_only"},
        content_type="application/json",
        **auth_header(admin),
    )
    assert inconsistent.status_code == 400

    created = client.post(
        "/api/plan-assignments/",
        {**base, "operating_classification": "transmit_only"},
        content_type="application/json",
        **auth_header(admin),
    )
    assert created.status_code == 201, created.content
    assert created.json()["operating_classification"] == "transmit_only"

    copied = client.post(
        f"/api/plan-revisions/{revision.id}/approve/",
        **auth_header(admin),
    )
    assert copied.status_code == 200, copied.content


@pytest.mark.django_db
def test_named_system_is_approvable_but_not_determined_is_not(client):
    admin, incident, period = setup_incident()
    _, revision = create_plan(client, admin, incident, period)
    named = client.post(
        "/api/plan-assignments/",
        {
            "revision": str(revision.id),
            "position": 1,
            "function": "Operations",
            "channel_name": "SYN TALKGROUP",
            "operating_classification": "named_system",
            "technology_subtype": "trunked_talkgroup",
        },
        content_type="application/json",
        **auth_header(admin),
    )
    assert named.status_code == 201, named.content

    undetermined = client.post(
        "/api/plan-assignments/",
        {
            "revision": str(revision.id),
            "position": 2,
            "function": "Planning",
            "channel_name": "SYN TBD",
            "operating_classification": "not_determined",
        },
        content_type="application/json",
        **auth_header(admin),
    )
    assert undetermined.status_code == 201, undetermined.content

    blocked = client.post(
        f"/api/plan-revisions/{revision.id}/approve/",
        **auth_header(admin),
    )
    assert blocked.status_code == 400
    assert "no determined operating classification" in json.dumps(blocked.json()).lower()


@pytest.mark.django_db
def test_reorder_requires_every_row_and_preserves_stable_positions(client):
    admin, incident, period = setup_incident()
    _, revision = create_plan(client, admin, incident, period)
    first = add_assignment(client, admin, revision, 1, "SYN CALL")
    second = add_assignment(client, admin, revision, 2, "SYN TAC")

    invalid = client.post(
        "/api/plan-assignments/reorder/",
        {"revision": str(revision.id), "assignment_ids": [str(second.id)]},
        content_type="application/json",
        **auth_header(admin),
    )
    assert invalid.status_code == 400

    response = client.post(
        "/api/plan-assignments/reorder/",
        {
            "revision": str(revision.id),
            "assignment_ids": [str(second.id), str(first.id)],
        },
        content_type="application/json",
        **auth_header(admin),
    )
    assert response.status_code == 200
    assert list(revision.assignments.values_list("id", flat=True)) == [second.id, first.id]


@pytest.mark.django_db
def test_pdf_is_approved_only_deterministic_and_audited(client):
    admin, incident, period = setup_incident()
    _, revision = create_plan(client, admin, incident, period)
    add_assignment(client, admin, revision, 1, "SYN CALL")

    draft_export = client.get(f"/api/plan-revisions/{revision.id}/pdf/", **auth_header(admin))
    assert draft_export.status_code == 400
    assert (
        client.post(f"/api/plan-revisions/{revision.id}/approve/", **auth_header(admin)).status_code
        == 200
    )

    first = client.get(f"/api/plan-revisions/{revision.id}/pdf/", **auth_header(admin))
    second = client.get(f"/api/plan-revisions/{revision.id}/pdf/", **auth_header(admin))
    assert first.status_code == 200
    assert first.content == second.content
    assert first["Content-Type"] == "application/pdf"
    reader = PdfReader(BytesIO(first.content))
    assert_flattened_pdf(reader)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "INCIDENT RADIO COMMUNICATIONS PLAN" in text
    assert "Synthetic Tornado Exercise" in text
    assert "SYN CALL" in text
    assert "Private Synthetic Contact" not in text
    assert "ICS 205" in text
    assert AuditEvent.objects.filter(action="plan_revision.pdf_exported").count() == 2


@pytest.mark.django_db
def test_contact_publication_requires_exact_preview_confirmation_and_audits_no_values(client):
    admin, incident, period = setup_incident()
    _, revision = create_plan(client, admin, incident, period)
    assignment = add_assignment(client, admin, revision, 1, "SYN CALL")
    configured = client.patch(
        f"/api/plan-assignments/{assignment.id}/",
        {
            "published_contact_fields": ["contact_name"],
            "contact_publication_purpose": "Synthetic gateway technical support",
            "contact_publication_placement": "special_instructions",
        },
        content_type="application/json",
        **auth_header(admin),
    )
    assert configured.status_code == 200, configured.content

    summary = client.get(
        f"/api/plan-revisions/{revision.id}/publication-summary/",
        **auth_header(admin),
    )
    assert summary.status_code == 200
    assert summary.json()["has_published_contacts"] is True
    assert summary.json()["contact_publications"][0]["fields"] == ["contact_name"]
    digest = summary.json()["digest"]

    preview = client.get(
        f"/api/plan-revisions/{revision.id}/approval-preview/",
        **auth_header(admin),
    )
    assert preview.status_code == 200
    assert preview["X-ICT-Contact-Publication-Digest"] == digest
    preview_text = "\n".join(
        page.extract_text() or "" for page in PdfReader(BytesIO(preview.content)).pages
    )
    assert "DRAFT APPROVAL PREVIEW" in preview_text
    assert "Special Instructions" in preview_text
    assert "Private Synthetic Contact" in preview_text

    unconfirmed = client.post(
        f"/api/plan-revisions/{revision.id}/approve/",
        {"confirm_contact_publication": False, "publication_digest": digest},
        content_type="application/json",
        **auth_header(admin),
    )
    assert unconfirmed.status_code == 400
    stale = client.post(
        f"/api/plan-revisions/{revision.id}/approve/",
        {
            "confirm_contact_publication": True,
            "publication_digest": "0" * 64,
        },
        content_type="application/json",
        **auth_header(admin),
    )
    assert stale.status_code == 400

    approved = client.post(
        f"/api/plan-revisions/{revision.id}/approve/",
        {
            "confirm_contact_publication": True,
            "publication_digest": digest,
        },
        content_type="application/json",
        **auth_header(admin),
    )
    assert approved.status_code == 200, approved.content
    exported = client.get(
        f"/api/plan-revisions/{revision.id}/pdf/",
        **auth_header(admin),
    )
    export_text = "\n".join(
        page.extract_text() or "" for page in PdfReader(BytesIO(exported.content)).pages
    )
    assert "Private Synthetic Contact" in export_text
    event = AuditEvent.objects.get(action="plan_revision.approved")
    assert event.details["contact_publication_digest"] == digest
    assert event.details["contact_publications"][0]["fields"] == ["contact_name"]
    assert event.details["contact_publications"][0]["placement"] == "special_instructions"
    assert "Private Synthetic Contact" not in json.dumps(event.details)


@pytest.mark.django_db
def test_pdf_continuation_pages_repeat_table_heading_and_page_numbers():
    admin, incident, period = setup_incident()
    plan = ICS205Plan.objects.create(incident=incident, operational_period=period, created_by=admin)
    revision = PlanRevision.objects.create(
        plan=plan,
        number=1,
        status=PlanRevision.Status.APPROVED,
        created_by=admin,
        approved_by=admin,
    )
    Assignment.objects.bulk_create(
        [
            Assignment(
                revision=revision,
                position=index,
                function="Tactical",
                channel_name=f"SYN TAC {index}",
                assignment="Synthetic operations",
                rx_frequency_hz=155_000_000 + index * 1000,
                tx_frequency_hz=155_000_000 + index * 1000,
                mode="Analog FM",
                remarks="Synthetic data only",
            )
            for index in range(1, 46)
        ]
    )
    reader = PdfReader(BytesIO(render_ics205(revision)))
    assert len(reader.pages) == 6
    assert_flattened_pdf(reader)
    for page_number, page in enumerate(reader.pages, 1):
        text = page.extract_text()
        assert "INCIDENT RADIO COMMUNICATIONS PLAN (ICS 205)" in text
        assert f"ICS 205 continuation {page_number} of 6" in text
    assert "SYN TAC 1" in reader.pages[0].extract_text()
    assert "SYN TAC 45" in reader.pages[-1].extract_text()


def test_official_fema_form_checksum_is_pinned():
    assert sha256(FORM_TEMPLATE.read_bytes()).hexdigest() == FORM_SHA256


@pytest.mark.django_db
def test_read_only_member_can_view_but_not_mutate_plan(client):
    admin, incident, period = setup_incident()
    plan, _ = create_plan(client, admin, incident, period)
    reader = get_user_model().objects.create_user("plan-reader", password="safe-test-password")
    UserRoleAssignment.objects.create(user=reader, role=Role.READ_ONLY)
    IncidentMembership.objects.create(
        incident=incident, user=reader, role=Role.READ_ONLY, assigned_by=admin
    )
    assert client.get("/api/ics205-plans/", **auth_header(reader)).status_code == 200
    response = client.patch(
        f"/api/ics205-plans/{plan.id}/",
        {"title": "Forbidden"},
        content_type="application/json",
        **auth_header(reader),
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_outsider_cannot_create_relationship_for_another_incident(client):
    admin, incident, period = setup_incident()
    _, revision = create_plan(client, admin, incident, period)
    first = add_assignment(client, admin, revision, 1, "SYN CALL")
    second = add_assignment(client, admin, revision, 2, "SYN TAC")
    outsider = get_user_model().objects.create_user(
        "relationship-outsider", password="safe-test-password"
    )
    UserRoleAssignment.objects.create(user=outsider, role=Role.COMT)

    response = client.post(
        "/api/plan-relationships/",
        {
            "revision": str(revision.id),
            "relationship_type": "patch",
            "assignments": [str(first.id), str(second.id)],
        },
        content_type="application/json",
        **auth_header(outsider),
    )
    assert response.status_code == 403
    assert AssignmentRelationship.objects.count() == 0
