import hashlib
import json

import pytest
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import ProtectedError
from rest_framework.authtoken.models import Token

from apps.accounts.models import Role, UserRoleAssignment
from apps.audit.models import AuditEvent
from apps.audit.services import record_event, record_export
from apps.incidents.models import Incident, IncidentMembership, OperationalPeriod
from apps.plans.models import Assignment, ICS205Plan, PlanRevision


def auth_header(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {"HTTP_AUTHORIZATION": f"Token {token.key}"}


def user_with_role(username, role):
    user = get_user_model().objects.create_user(username, password="safe-test-password")
    UserRoleAssignment.objects.create(user=user, role=role)
    return user


def incident_for(user, suffix):
    incident = Incident.objects.create(
        name=f"Synthetic Audit Exercise {suffix}",
        incident_number=f"SYN-AUDIT-{suffix}",
        created_by=user,
    )
    IncidentMembership.objects.create(
        incident=incident,
        user=user,
        role=Role.COML,
        assigned_by=user,
    )
    return incident


def draft_assignment_for(user, incident):
    period = OperationalPeriod.objects.create(
        incident=incident,
        name="Synthetic Operational Period",
        starts_at="2026-07-27T08:00:00Z",
        ends_at="2026-07-27T20:00:00Z",
        created_by=user,
    )
    plan = ICS205Plan.objects.create(
        incident=incident,
        operational_period=period,
        created_by=user,
    )
    revision = PlanRevision.objects.create(plan=plan, number=1, created_by=user)
    assignment = Assignment.objects.create(
        revision=revision,
        position=1,
        function="Command",
        channel_name="SYN CALL",
        assignment="Synthetic exercise",
        resource_snapshot={"type": "incident", "name": "SYN CALL"},
    )
    return revision, assignment


@pytest.mark.django_db
def test_unauthenticated_mutation_is_denied_without_a_success_audit_event(client):
    owner = user_with_role("audit-owner", Role.COML)
    incident = incident_for(owner, "NOAUTH")

    response = client.patch(
        f"/api/incidents/{incident.id}/",
        {"name": "Unauthorized change"},
        content_type="application/json",
    )

    assert response.status_code == 401
    incident.refresh_from_db()
    assert incident.name == "Synthetic Audit Exercise NOAUTH"
    assert not AuditEvent.objects.exists()


@pytest.mark.django_db
def test_cross_incident_mutation_is_hidden_and_does_not_poison_the_audit_log(client):
    owner = user_with_role("audit-incident-owner", Role.COML)
    outsider = user_with_role("audit-outsider", Role.COMT)
    incident = incident_for(owner, "SCOPE")

    response = client.patch(
        f"/api/incidents/{incident.id}/",
        {"name": "Cross-incident change"},
        content_type="application/json",
        **auth_header(outsider),
    )

    assert response.status_code == 404
    incident.refresh_from_db()
    assert incident.name == "Synthetic Audit Exercise SCOPE"
    assert not AuditEvent.objects.exists()


@pytest.mark.django_db
def test_audit_append_failure_rolls_back_the_material_api_mutation(client, monkeypatch):
    owner = user_with_role("audit-rollback-owner", Role.COML)
    incident = incident_for(owner, "ROLLBACK")

    def fail_audit_append(**kwargs):
        raise RuntimeError("synthetic audit append failure")

    monkeypatch.setattr("apps.incidents.views.record_event", fail_audit_append)

    response = client.patch(
        f"/api/incidents/{incident.id}/",
        {"name": "Must roll back"},
        content_type="application/json",
        **auth_header(owner),
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "An unexpected error occurred."}
    incident.refresh_from_db()
    assert incident.name == "Synthetic Audit Exercise ROLLBACK"
    assert not AuditEvent.objects.exists()


@pytest.mark.django_db
def test_protected_assignment_values_are_not_copied_into_audit_details(client):
    owner = user_with_role("audit-contact-owner", Role.COML)
    incident = incident_for(owner, "CONTACT")
    _, assignment = draft_assignment_for(owner, incident)
    protected_values = {
        "contact_name": "SYNTHETIC PRIVATE CONTACT MARKER",
        "site_address": "SYNTHETIC PRIVATE ADDRESS MARKER",
        "phone_numbers": "SYNTHETIC PRIVATE PHONE MARKER",
        "contact_24_hour": "SYNTHETIC PRIVATE 24-HOUR MARKER",
    }

    response = client.patch(
        f"/api/plan-assignments/{assignment.id}/",
        protected_values,
        content_type="application/json",
        **auth_header(owner),
    )

    assert response.status_code == 200
    event = AuditEvent.objects.get(action="plan_assignment.updated")
    assert event.details == {"changed_fields": sorted(protected_values)}
    serialized_details = json.dumps(event.details)
    for protected_value in protected_values.values():
        assert protected_value not in serialized_details


@pytest.mark.django_db
def test_application_orm_cannot_rewrite_or_remove_an_audit_event():
    owner = user_with_role("audit-append-owner", Role.COML)
    incident = incident_for(owner, "APPEND")
    event = record_event(actor=owner, action="incident.created", target=incident)

    event.action = "forged.action"
    with pytest.raises(RuntimeError, match="append-only"):
        event.save()
    with pytest.raises(RuntimeError, match="append-only"):
        event.delete()
    with pytest.raises(RuntimeError, match="append-only"):
        AuditEvent.objects.filter(pk=event.pk).update(action="forged.action")
    with pytest.raises(RuntimeError, match="append-only"):
        AuditEvent.objects.filter(pk=event.pk).delete()
    with pytest.raises(RuntimeError, match="append-only"):
        with transaction.atomic():
            AuditEvent.objects.bulk_update([event], ["action"])

    event.refresh_from_db()
    assert event.action == "incident.created"


@pytest.mark.django_db
def test_deleting_an_actor_cannot_erase_audit_attribution():
    owner = user_with_role("audit-target-owner", Role.COML)
    actor = user_with_role("audit-protected-actor", Role.COMT)
    incident = incident_for(owner, "ACTOR")
    event = record_event(actor=actor, action="incident.reviewed", target=incident)

    with pytest.raises(ProtectedError) as exc_info:
        actor.delete()

    assert event in exc_info.value.protected_objects
    assert AuditEvent.objects.filter(pk=event.pk, actor=actor).exists()


@pytest.mark.django_db
def test_export_audit_callers_cannot_override_authoritative_digest_metadata():
    owner = user_with_role("audit-export-owner", Role.COML)
    incident = incident_for(owner, "EXPORT")
    revision, _ = draft_assignment_for(owner, incident)
    content = b"synthetic export bytes"

    event = record_export(
        actor=owner,
        action="plan_revision.pdf_exported",
        revision=revision,
        export_format="pdf",
        content=content,
        details={
            "filename": "synthetic.pdf",
            "format": "forged",
            "content_sha256": "f" * 64,
            "byte_size": 1,
            "revision_number": 999,
            "revision_status": "forged",
        },
    )

    assert event.details == {
        "filename": "synthetic.pdf",
        "format": "pdf",
        "content_sha256": hashlib.sha256(content).hexdigest(),
        "byte_size": len(content),
        "revision_number": revision.number,
        "revision_status": revision.status,
    }


@pytest.mark.django_db
def test_export_digest_replay_is_bound_to_the_original_revision_and_format(client):
    owner = user_with_role("audit-replay-owner", Role.COML)
    first_incident = incident_for(owner, "REPLAY-1")
    second_incident = incident_for(owner, "REPLAY-2")
    first_revision, _ = draft_assignment_for(owner, first_incident)
    second_revision, _ = draft_assignment_for(owner, second_incident)
    content = b"synthetic replay candidate"
    digest = hashlib.sha256(content).hexdigest()
    record_export(
        actor=owner,
        action="plan_revision.pdf_exported",
        revision=first_revision,
        export_format="pdf",
        content=content,
    )

    wrong_revision = client.post(
        f"/api/audit/revisions/{second_revision.id}/exports/pdf/verify/",
        {"content_sha256": digest},
        content_type="application/json",
        **auth_header(owner),
    )
    wrong_format = client.post(
        f"/api/audit/revisions/{first_revision.id}/exports/geojson/verify/",
        {"content_sha256": digest},
        content_type="application/json",
        **auth_header(owner),
    )

    assert wrong_revision.status_code == 200
    assert wrong_revision.json()["verified"] is False
    assert wrong_format.status_code == 200
    assert wrong_format.json()["verified"] is False
