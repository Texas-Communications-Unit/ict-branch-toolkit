import uuid
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token

from apps.accounts.external_identity import (
    ExternalIdentityAssertion,
    provision_shadow_identity,
)
from apps.accounts.models import ExternalIdentity, Role, UserRoleAssignment
from apps.audit.models import AuditEvent
from apps.collaboration.models import (
    CollaborationChange,
    CollaborationResolution,
    PresenceLease,
    SensitiveFieldRule,
)
from apps.incidents.models import Incident, IncidentMembership, OperationalPeriod
from apps.plans.models import Assignment, ICS205Plan, PlanRevision


def auth_header(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {"HTTP_AUTHORIZATION": f"Token {token.key}"}


def setup_workspace():
    admin = get_user_model().objects.create_superuser(
        "collaboration-admin",
        "collaboration-admin@example.invalid",
        "safe-test-password",
    )
    incident = Incident.objects.create(
        name="Synthetic Collaboration Exercise",
        incident_number="SYN-COLLAB",
        created_by=admin,
    )
    IncidentMembership.objects.create(
        incident=incident,
        user=admin,
        role=Role.ADMINISTRATOR,
        assigned_by=admin,
    )
    period = OperationalPeriod.objects.create(
        incident=incident,
        name="Operational Period 1",
        starts_at="2026-07-28T08:00:00Z",
        ends_at="2026-07-28T20:00:00Z",
        created_by=admin,
    )
    plan = ICS205Plan.objects.create(
        incident=incident,
        operational_period=period,
        title="Synthetic ICS-205",
        created_by=admin,
    )
    revision = PlanRevision.objects.create(plan=plan, number=1, created_by=admin)
    return admin, incident, revision


def create_assignment(revision, position, name):
    return Assignment.objects.create(
        revision=revision,
        position=position,
        function="Command",
        channel_name=name,
        assignment="Synthetic exercise",
        rx_frequency_hz=155_000_000 + position * 1_000,
        tx_frequency_hz=155_000_000 + position * 1_000,
        mode="Analog FM",
        remarks="Initial",
        contact_name="Synthetic Restricted Contact",
        resource_snapshot={"source": "synthetic-test-fixture"},
    )


def mutation_payload(revision, operation, base_version, changes, *, object_id=None):
    return {
        "client_mutation_id": str(uuid.uuid4()),
        "device_id": str(uuid.uuid4()),
        "revision": str(revision.id),
        "operation": operation,
        "object_id": str(object_id) if object_id else None,
        "section": "ics205",
        "base_version": base_version,
        "changes": changes,
    }


@pytest.mark.django_db
def test_independent_assignment_changes_succeed_without_last_write_wins(client):
    admin, _, revision = setup_workspace()
    first = create_assignment(revision, 1, "SYN CALL")
    second = create_assignment(revision, 2, "SYN TAC")
    headers = auth_header(admin)

    first_response = client.post(
        "/api/collaboration/mutations/",
        mutation_payload(
            revision,
            "assignment.update",
            1,
            {"remarks": "First editor"},
            object_id=first.id,
        ),
        content_type="application/json",
        **headers,
    )
    second_response = client.post(
        "/api/collaboration/mutations/",
        mutation_payload(
            revision,
            "assignment.update",
            1,
            {"remarks": "Second editor"},
            object_id=second.id,
        ),
        content_type="application/json",
        **headers,
    )

    assert first_response.status_code == 200, first_response.content
    assert second_response.status_code == 200, second_response.content
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.remarks == "First editor"
    assert second.remarks == "Second editor"
    assert first.collaboration_version == second.collaboration_version == 2


@pytest.mark.django_db
def test_stale_same_record_change_is_retained_as_conflict_and_can_be_resolved(client):
    admin, _, revision = setup_workspace()
    assignment = create_assignment(revision, 1, "SYN CALL")
    headers = auth_header(admin)
    saved_payload = mutation_payload(
        revision,
        "assignment.update",
        1,
        {"remarks": "Saved first"},
        object_id=assignment.id,
    )
    stale_payload = mutation_payload(
        revision,
        "assignment.update",
        1,
        {"remarks": "Stale proposal"},
        object_id=assignment.id,
    )

    saved = client.post(
        "/api/collaboration/mutations/",
        saved_payload,
        content_type="application/json",
        **headers,
    )
    conflict = client.post(
        "/api/collaboration/mutations/",
        stale_payload,
        content_type="application/json",
        **headers,
    )

    assert saved.status_code == 200
    assert conflict.status_code == 409, conflict.content
    assert conflict.json()["disposition"] == CollaborationChange.Disposition.CONFLICT
    assert conflict.json()["proposed_snapshot"]["remarks"] == "Stale proposal"
    assert conflict.json()["current_snapshot"]["remarks"] == "Saved first"
    assignment.refresh_from_db()
    assert assignment.remarks == "Saved first"

    resolved = client.post(
        f"/api/collaboration/conflicts/{conflict.json()['id']}/resolve/",
        {"decision": "discard", "explanation": "Keep the previously saved field value."},
        content_type="application/json",
        **headers,
    )
    assert resolved.status_code == 201, resolved.content
    assert CollaborationResolution.objects.filter(conflict_id=conflict.json()["id"]).exists()
    assert AuditEvent.objects.filter(action="collaboration.conflict_resolved").exists()


@pytest.mark.django_db
def test_duplicate_mutation_is_idempotent_but_identifier_reuse_is_rejected(client):
    admin, _, revision = setup_workspace()
    assignment = create_assignment(revision, 1, "SYN CALL")
    headers = auth_header(admin)
    payload = mutation_payload(
        revision,
        "assignment.update",
        1,
        {"remarks": "Exactly once"},
        object_id=assignment.id,
    )

    first = client.post(
        "/api/collaboration/mutations/",
        payload,
        content_type="application/json",
        **headers,
    )
    repeated = client.post(
        "/api/collaboration/mutations/",
        payload,
        content_type="application/json",
        **headers,
    )
    reused = client.post(
        "/api/collaboration/mutations/",
        {**payload, "changes": {"remarks": "Different payload"}},
        content_type="application/json",
        **headers,
    )

    assert repeated.status_code == 200
    assert repeated.json()["id"] == first.json()["id"]
    assert CollaborationChange.objects.count() == 1
    assert reused.status_code == 400
    assignment.refresh_from_db()
    assert assignment.collaboration_version == 2


@pytest.mark.django_db
def test_mutation_metadata_cannot_be_used_as_unbounded_or_sensitive_presence_text(client):
    admin, _, revision = setup_workspace()
    headers = auth_header(admin)
    unsupported_section = client.post(
        "/api/collaboration/presence/",
        {
            "revision": str(revision.id),
            "device_id": str(uuid.uuid4()),
            "section": "phone-555-0100",
            "mode": "viewing",
        },
        content_type="application/json",
        **headers,
    )
    oversized = client.post(
        "/api/collaboration/mutations/",
        mutation_payload(
            revision,
            "revision.update",
            1,
            {"prepared_by_name": "X" * 70_000},
        ),
        content_type="application/json",
        **headers,
    )

    assert unsupported_section.status_code == 400
    assert oversized.status_code == 400
    assert CollaborationChange.objects.count() == 0


@pytest.mark.django_db
def test_approved_revision_rejects_and_retains_online_mutation(client):
    admin, _, revision = setup_workspace()
    revision.status = PlanRevision.Status.APPROVED
    revision.approved_by = admin
    revision.approved_at = timezone.now()
    revision.save()
    payload = mutation_payload(
        revision,
        "revision.update",
        revision.collaboration_version,
        {"prepared_by_position": "COML"},
    )

    response = client.post(
        "/api/collaboration/mutations/",
        payload,
        content_type="application/json",
        **auth_header(admin),
    )

    assert response.status_code == 400
    assert response.json()["disposition"] == CollaborationChange.Disposition.REJECTED
    revision.refresh_from_db()
    assert revision.prepared_by_position == ""


@pytest.mark.django_db
def test_presence_expires_and_revoked_membership_fails_on_next_request(client):
    admin, incident, revision = setup_workspace()
    editor = get_user_model().objects.create_user(
        "collaboration-editor",
        password="safe-test-password",
    )
    UserRoleAssignment.objects.create(user=editor, role=Role.READ_ONLY)
    membership = IncidentMembership.objects.create(
        incident=incident,
        user=editor,
        role=Role.COMT,
        assigned_by=admin,
    )
    device_id = str(uuid.uuid4())
    headers = auth_header(editor)

    heartbeat = client.post(
        "/api/collaboration/presence/",
        {
            "revision": str(revision.id),
            "device_id": device_id,
            "section": "ics205.assignments",
            "mode": "editing",
        },
        content_type="application/json",
        **headers,
    )
    assert heartbeat.status_code == 201, heartbeat.content
    listed = client.get(
        f"/api/collaboration/presence/?revision={revision.id}&section=ics205.assignments",
        **headers,
    )
    assert listed.status_code == 200
    assert listed.json()[0]["display_name"] == "collaboration-editor"

    lease = PresenceLease.objects.get()
    lease.expires_at = timezone.now() - timedelta(seconds=1)
    lease.save(update_fields=["expires_at"])
    assert (
        client.get(
            f"/api/collaboration/presence/?revision={revision.id}",
            **headers,
        ).json()
        == []
    )

    membership.is_active = False
    membership.save(update_fields=["is_active"])
    denied = client.post(
        "/api/collaboration/presence/",
        {
            "revision": str(revision.id),
            "device_id": device_id,
            "section": "ics205",
            "mode": "viewing",
        },
        content_type="application/json",
        **headers,
    )
    assert denied.status_code == 403


@pytest.mark.django_db
def test_restricted_assignment_fields_are_omitted_and_edits_fail_closed(client):
    admin, incident, revision = setup_workspace()
    assignment = create_assignment(revision, 1, "SYN CALL")
    technician = get_user_model().objects.create_user(
        "restricted-technician",
        password="safe-test-password",
    )
    UserRoleAssignment.objects.create(user=technician, role=Role.READ_ONLY)
    IncidentMembership.objects.create(
        incident=incident,
        user=technician,
        role=Role.COMT,
        assigned_by=admin,
    )
    headers = auth_header(technician)

    plans = client.get("/api/ics205-plans/", **headers)
    assert plans.status_code == 200
    row = plans.json()["results"][0]["revisions"][0]["assignments"][0]
    assert "contact_name" not in row

    denied = client.post(
        "/api/collaboration/mutations/",
        mutation_payload(
            revision,
            "assignment.update",
            assignment.collaboration_version,
            {"contact_name": "Unauthorized change"},
            object_id=assignment.id,
        ),
        content_type="application/json",
        **headers,
    )
    assert denied.status_code == 400
    assert denied.json()["disposition"] == CollaborationChange.Disposition.REJECTED
    assignment.refresh_from_db()
    assert assignment.contact_name == "Synthetic Restricted Contact"

    rule = SensitiveFieldRule.objects.create(
        incident=incident,
        field_name="contact_name",
        unauthorized_visibility=SensitiveFieldRule.Visibility.REDACTED,
        view_roles=[Role.ADMINISTRATOR],
        edit_roles=[Role.ADMINISTRATOR],
        created_by=admin,
        updated_by=admin,
    )
    redacted = client.get("/api/ics205-plans/", **headers).json()["results"][0]["revisions"][0][
        "assignments"
    ][0]
    assert redacted["contact_name"] == "[REDACTED]"
    assert rule.version == 1


@pytest.mark.django_db
def test_external_identity_boundary_is_disabled_and_shadow_accounts_have_no_password(client):
    admin, _, _ = setup_workspace()
    status_response = client.get(
        "/api/external-identity/status/",
        **auth_header(admin),
    )
    assert status_response.status_code == 200
    assert status_response.json()["enabled"] is False
    assert status_response.json()["password_passthrough"] is False
    assert status_response.json()["live_connection"] is False

    assertion = ExternalIdentityAssertion(
        provider="synthetic-authority",
        external_subject="synthetic-subject-1",
        civicrm_contact_id="synthetic-contact-1",
        display_name="Synthetic COML",
        eligible=True,
        role_keys=("approved-coml",),
        valid_until=timezone.now() + timedelta(hours=1),
    )
    with override_settings(
        ICT_EXTERNAL_SSO_ENABLED=True,
        ICT_EXTERNAL_ROLE_MAPPINGS={Role.COML: ["approved-coml"]},
    ):
        identity = provision_shadow_identity(assertion)

    assert identity.eligibility == ExternalIdentity.Eligibility.ELIGIBLE
    assert identity.mapped_role == Role.COML
    assert identity.user.has_usable_password() is False
    assert identity.user.toolkit_role.role == Role.COML
    event = AuditEvent.objects.get(action="external_identity.shadow_created")
    assert "role_keys" not in event.details
    assert "external_subject" not in event.details
