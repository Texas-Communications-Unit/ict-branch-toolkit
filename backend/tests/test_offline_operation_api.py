import json
import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token

from apps.accounts.models import Role, UserRoleAssignment
from apps.audit.models import AuditEvent
from apps.incidents.models import Incident, IncidentMembership, OperationalPeriod
from apps.offline.models import (
    OfflineConflictResolution,
    OfflineMutationReceipt,
    OfflinePackage,
)
from apps.offline.services import MUTATION_SCHEMA_VERSION, digest
from apps.plans.models import Assignment, ICS205Plan, PlanRevision
from apps.resources.models import ConventionalChannel, ResourceRelease, ResourceSource
from apps.sites.models import RadioSite


def auth_header(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {"HTTP_AUTHORIZATION": f"Token {token.key}"}


def post_json(client, path, payload, user):
    return client.post(
        path,
        data=json.dumps(payload),
        content_type="application/json",
        **auth_header(user),
    )


def user_with_role(username, role=Role.COML):
    user = get_user_model().objects.create_user(
        username,
        password="safe-test-password",
    )
    UserRoleAssignment.objects.create(user=user, role=role)
    return user


def offline_fixture(username="offline-owner"):
    owner = user_with_role(username)
    incident = Incident.objects.create(
        name="Synthetic offline exercise",
        incident_number=f"SYN-OFFLINE-{username}",
        created_by=owner,
    )
    membership = IncidentMembership.objects.create(
        incident=incident,
        user=owner,
        role=Role.COML,
        assigned_by=owner,
    )
    period = OperationalPeriod.objects.create(
        incident=incident,
        name="Synthetic operational period",
        starts_at=timezone.now(),
        ends_at=timezone.now() + timedelta(hours=12),
        created_by=owner,
    )
    plan = ICS205Plan.objects.create(
        incident=incident,
        operational_period=period,
        title="Synthetic offline ICS-205",
        created_by=owner,
    )
    revision = PlanRevision.objects.create(
        plan=plan,
        number=1,
        prepared_by_name="Synthetic Planner",
        created_by=owner,
    )
    assignment = Assignment.objects.create(
        revision=revision,
        position=1,
        function="Command",
        channel_name="SYN CALL",
        assignment="Synthetic exercise only",
        rx_frequency_hz=155_000_000,
        tx_frequency_hz=155_000_000,
        mode="Analog FM",
        remarks="Original synthetic note",
        resource_snapshot={"classification": "synthetic-test-only"},
    )
    return owner, incident, membership, revision, assignment


def create_package(client, owner, incident, revision, device_id=None, **selection):
    device_id = device_id or uuid.uuid4()
    response = post_json(
        client,
        "/api/offline-packages/",
        {
            "incident": str(incident.id),
            "device_id": str(device_id),
            "expires_in_hours": 24,
            "selection": {
                "revision_ids": [str(revision.id)],
                "resource_release_ids": [],
                "site_ids": [],
                "terrain_analysis_ids": [],
                "attachment_ids": [],
                "include_map": False,
                **selection,
            },
        },
        owner,
    )
    assert response.status_code == 201, response.content
    return OfflinePackage.objects.get(pk=response.json()["id"]), device_id


def iso(value):
    return value.isoformat().replace("+00:00", "Z")


def mutation_payload(
    *,
    package,
    owner,
    device_id,
    sequence,
    previous_hash,
    operation,
    revision,
    object_id,
    payload,
    base_updated_at=None,
    mutation_id=None,
):
    mutation_id = mutation_id or uuid.uuid4()
    occurred_at = timezone.now()
    payload_sha256 = digest(payload)
    document = {
        "schema_version": MUTATION_SCHEMA_VERSION,
        "package_id": str(package.id),
        "mutation_id": str(mutation_id),
        "sequence": sequence,
        "actor_id": owner.pk,
        "device_id": str(device_id),
        "operation": operation,
        "object_id": str(object_id) if object_id else None,
        "revision_id": str(revision.id),
        "previous_hash": previous_hash,
        "payload_sha256": payload_sha256,
        "base_updated_at": iso(base_updated_at) if base_updated_at else None,
        "occurred_at_client": iso(occurred_at),
    }
    return {
        "id": str(mutation_id),
        "sequence": sequence,
        "actor_id": owner.pk,
        "device_id": str(device_id),
        "operation": operation,
        "object_id": str(object_id) if object_id else None,
        "revision_id": str(revision.id),
        "previous_hash": previous_hash,
        "payload_sha256": payload_sha256,
        "mutation_sha256": digest(document),
        "payload": payload,
        "base_updated_at": iso(base_updated_at) if base_updated_at else None,
        "occurred_at_client": iso(occurred_at),
    }


def synchronize(client, owner, package, mutations, client_now=None):
    return post_json(
        client,
        f"/api/offline-packages/{package.id}/synchronize/",
        {
            "client_now": iso(client_now or timezone.now()),
            "mutations": mutations,
        },
        owner,
    )


@pytest.mark.django_db
def test_offline_status_is_fail_closed_by_default(client):
    owner = user_with_role("offline-status")
    response = client.get("/api/offline-status/", **auth_header(owner))
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    assert body["approved_for_non_synthetic_use"] is False
    assert "assignment.update" in body["supported_operations"]
    assert any("approve" in item for item in body["unsupported_operations"])
    assert "No last-writer-wins" in body["conflict_policy"]

    owner, incident, _, revision, _ = offline_fixture("offline-disabled")
    blocked = post_json(
        client,
        "/api/offline-packages/",
        {
            "incident": str(incident.id),
            "device_id": str(uuid.uuid4()),
            "selection": {"revision_ids": [str(revision.id)]},
        },
        owner,
    )
    assert blocked.status_code == 400
    assert OfflinePackage.objects.count() == 0


@pytest.mark.django_db
@override_settings(ICT_OFFLINE_ENABLED=True)
def test_package_contains_only_explicit_scope_and_audited_manifest(client):
    owner, incident, _, revision, assignment = offline_fixture("offline-package")
    package, device_id = create_package(client, owner, incident, revision)
    response = client.get(
        f"/api/offline-packages/{package.id}/",
        **auth_header(owner),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["device_id"] == str(device_id)
    assert body["payload_snapshot"]["incident"]["id"] == str(incident.id)
    assert [item["id"] for item in body["payload_snapshot"]["revisions"]] == [str(revision.id)]
    assert body["payload_snapshot"]["revisions"][0]["assignments"][0]["id"] == str(assignment.id)
    assert body["payload_snapshot"]["resource_releases"] == []
    assert body["payload_snapshot"]["sites"] == []
    assert body["payload_snapshot"]["terrain_analyses"] == []
    assert body["payload_snapshot"]["attachments"] == []
    assert body["manifest"]["payload_bytes"] <= 5_242_880
    assert body["last_chain_sha256"] == body["manifest_sha256"]
    assert AuditEvent.objects.filter(
        action="offline_package.created",
        target_id=str(package.id),
    ).exists()


@pytest.mark.django_db
@override_settings(ICT_OFFLINE_ENABLED=True)
def test_ordered_tamper_evident_update_and_duplicate_are_idempotent(client):
    owner, incident, _, revision, assignment = offline_fixture("offline-sync")
    package, device_id = create_package(client, owner, incident, revision)
    mutation = mutation_payload(
        package=package,
        owner=owner,
        device_id=device_id,
        sequence=1,
        previous_hash=package.manifest_sha256,
        operation="assignment.update",
        revision=revision,
        object_id=assignment.id,
        payload={"remarks": "Queued synthetic offline note"},
        base_updated_at=assignment.updated_at,
    )
    applied = synchronize(client, owner, package, [mutation])
    assert applied.status_code == 200, applied.content
    assert applied.json()["partial"] is False
    assert applied.json()["results"][0]["status"] == "applied"
    assignment.refresh_from_db()
    assert assignment.remarks == "Queued synthetic offline note"

    duplicate = synchronize(client, owner, package, [mutation])
    assert duplicate.status_code == 200, duplicate.content
    assert duplicate.json()["partial"] is True
    assert duplicate.json()["results"][0]["status"] == "duplicate"
    assert OfflineMutationReceipt.objects.count() == 1
    assert AuditEvent.objects.filter(action="offline_assignment_update.applied").count() == 1


@pytest.mark.django_db
@override_settings(ICT_OFFLINE_ENABLED=True)
def test_supported_revision_create_and_delete_operations_preserve_order(client):
    owner, incident, _, revision, _ = offline_fixture("offline-operations")
    package, device_id = create_package(client, owner, incident, revision)
    first = mutation_payload(
        package=package,
        owner=owner,
        device_id=device_id,
        sequence=1,
        previous_hash=package.manifest_sha256,
        operation="revision.update",
        revision=revision,
        object_id=revision.id,
        payload={"prepared_by_position": "COML"},
    )
    assignment_id = uuid.uuid4()
    second = mutation_payload(
        package=package,
        owner=owner,
        device_id=device_id,
        sequence=2,
        previous_hash=first["mutation_sha256"],
        operation="assignment.create",
        revision=revision,
        object_id=assignment_id,
        payload={
            "position": 2,
            "function": "Tactical",
            "channel_name": "SYN TAC",
            "assignment": "Synthetic offline assignment",
            "rx_frequency_hz": 155_010_000,
            "tx_frequency_hz": 155_010_000,
            "mode": "Analog FM",
            "remarks": "Synthetic queue-created row",
        },
    )
    applied = synchronize(client, owner, package, [first, second])
    assert applied.status_code == 200, applied.content
    assert [item["status"] for item in applied.json()["results"]] == [
        "applied",
        "applied",
    ]
    revision.refresh_from_db()
    created = Assignment.objects.get(pk=assignment_id)
    assert revision.prepared_by_position == "COML"
    assert created.channel_name == "SYN TAC"

    delete_package, delete_device = create_package(
        client,
        owner,
        incident,
        revision,
    )
    deletion = mutation_payload(
        package=delete_package,
        owner=owner,
        device_id=delete_device,
        sequence=1,
        previous_hash=delete_package.manifest_sha256,
        operation="assignment.delete",
        revision=revision,
        object_id=created.id,
        payload={},
        base_updated_at=created.updated_at,
    )
    deleted = synchronize(client, owner, delete_package, [deletion])
    assert deleted.status_code == 200, deleted.content
    assert deleted.json()["results"][0]["status"] == "applied"
    assert not Assignment.objects.filter(pk=assignment_id).exists()


@pytest.mark.django_db
@override_settings(ICT_OFFLINE_ENABLED=True)
def test_resources_and_sites_outside_explicit_package_scope_are_rejected(client):
    owner, incident, _, revision, _ = offline_fixture("offline-scope")
    source = ResourceSource.objects.create(
        slug="synthetic-offline-scope",
        name="Synthetic offline scope release",
        source_type=ResourceSource.Type.SYNTHETIC,
    )
    release = ResourceRelease.objects.create(
        source=source,
        version="SYN-OFFLINE-1",
        effective_status=ResourceRelease.Status.EFFECTIVE,
        content_sha256="a" * 64,
        permitted_use="Synthetic tests only.",
        imported_by=owner,
    )
    channel = ConventionalChannel.objects.create(
        release=release,
        identifier="SYN-OFF-1",
        name="Synthetic out-of-scope channel",
        rx_frequency_hz=155_020_000,
        tx_frequency_hz=155_020_000,
        mode=ConventionalChannel.Mode.ANALOG_FM,
    )
    package, device_id = create_package(client, owner, incident, revision)
    mutation = mutation_payload(
        package=package,
        owner=owner,
        device_id=device_id,
        sequence=1,
        previous_hash=package.manifest_sha256,
        operation="assignment.create",
        revision=revision,
        object_id=uuid.uuid4(),
        payload={
            "position": 2,
            "function": "Tactical",
            "channel_name": channel.name,
            "conventional_channel": str(channel.id),
        },
    )
    rejected = synchronize(client, owner, package, [mutation])
    assert rejected.status_code == 200, rejected.content
    assert rejected.json()["results"][0]["status"] == "rejected"
    assert rejected.json()["results"][0]["result"]["code"] == "invalid_payload"

    other_owner, other_incident, _, _, _ = offline_fixture("offline-other-site")
    other_site = RadioSite.objects.create(
        incident=other_incident,
        name="Synthetic out-of-scope site",
        latitude=Decimal("33.000000"),
        longitude=Decimal("-97.000000"),
        coordinate_format=RadioSite.CoordinateFormat.DECIMAL,
        created_by=other_owner,
    )
    outside_site = post_json(
        client,
        "/api/offline-packages/",
        {
            "incident": str(incident.id),
            "device_id": str(uuid.uuid4()),
            "expires_in_hours": 24,
            "selection": {
                "revision_ids": [str(revision.id)],
                "resource_release_ids": [],
                "site_ids": [str(other_site.id)],
                "terrain_analysis_ids": [],
                "attachment_ids": [],
                "include_map": True,
            },
        },
        owner,
    )
    assert outside_site.status_code == 400


@pytest.mark.django_db
@override_settings(ICT_OFFLINE_ENABLED=True)
def test_broken_chain_reordered_queue_and_clock_skew_fail_without_changes(client):
    owner, incident, _, revision, assignment = offline_fixture("offline-tamper")
    package, device_id = create_package(client, owner, incident, revision)
    mutation = mutation_payload(
        package=package,
        owner=owner,
        device_id=device_id,
        sequence=2,
        previous_hash="f" * 64,
        operation="assignment.update",
        revision=revision,
        object_id=assignment.id,
        payload={"remarks": "Must not apply"},
        base_updated_at=assignment.updated_at,
    )
    broken = synchronize(client, owner, package, [mutation])
    assert broken.status_code == 400
    assignment.refresh_from_db()
    assert assignment.remarks == "Original synthetic note"

    mutation["sequence"] = 1
    skewed = synchronize(
        client,
        owner,
        package,
        [mutation],
        client_now=timezone.now() - timedelta(hours=1),
    )
    assert skewed.status_code == 400
    assert "clock" in skewed.content.decode().lower()
    assert OfflineMutationReceipt.objects.count() == 0


@pytest.mark.django_db
@override_settings(ICT_OFFLINE_ENABLED=True)
def test_stale_base_requires_explicit_resolution_and_blocks_later_changes(client):
    owner, incident, _, revision, assignment = offline_fixture("offline-conflict")
    package, device_id = create_package(client, owner, incident, revision)
    packaged_assignment_updated_at = assignment.updated_at
    assignment.remarks = "Server-side concurrent change"
    assignment.save()

    first = mutation_payload(
        package=package,
        owner=owner,
        device_id=device_id,
        sequence=1,
        previous_hash=package.manifest_sha256,
        operation="assignment.update",
        revision=revision,
        object_id=assignment.id,
        payload={"remarks": "Offline conflicting change"},
        base_updated_at=packaged_assignment_updated_at,
    )
    second = mutation_payload(
        package=package,
        owner=owner,
        device_id=device_id,
        sequence=2,
        previous_hash=first["mutation_sha256"],
        operation="revision.update",
        revision=revision,
        object_id=revision.id,
        payload={"prepared_by_position": "COML"},
    )
    response = synchronize(client, owner, package, [first, second])
    assert response.status_code == 200, response.content
    assert [item["status"] for item in response.json()["results"]] == [
        "conflict",
        "conflict",
    ]
    assert response.json()["results"][0]["result"]["code"] == "stale_base_revision"
    assert response.json()["results"][1]["result"]["code"] == "earlier_conflict_unresolved"
    revision.refresh_from_db()
    assignment.refresh_from_db()
    assert revision.prepared_by_position == ""
    assert assignment.remarks == "Server-side concurrent change"

    resolved = post_json(
        client,
        f"/api/offline-packages/{package.id}/resolve/",
        {
            "mutation_id": first["id"],
            "decision": "discard",
            "explanation": "Keep the documented server-side synthetic change.",
        },
        owner,
    )
    assert resolved.status_code == 201, resolved.content
    assert OfflineConflictResolution.objects.filter(receipt_id=first["id"]).exists()


@pytest.mark.django_db
@override_settings(ICT_OFFLINE_ENABLED=True)
def test_approved_revision_is_read_only_and_never_rewritten(client):
    owner, incident, _, revision, assignment = offline_fixture("offline-approved")
    package, device_id = create_package(client, owner, incident, revision)
    revision.status = PlanRevision.Status.APPROVED
    revision.approved_by = owner
    revision.approved_at = timezone.now()
    revision.save()
    mutation = mutation_payload(
        package=package,
        owner=owner,
        device_id=device_id,
        sequence=1,
        previous_hash=package.manifest_sha256,
        operation="assignment.update",
        revision=revision,
        object_id=assignment.id,
        payload={"remarks": "Forbidden offline rewrite"},
        base_updated_at=assignment.updated_at,
    )
    response = synchronize(client, owner, package, [mutation])
    assert response.status_code == 200
    assert response.json()["results"][0]["status"] == "conflict"
    assert response.json()["results"][0]["result"]["code"] == "revision_locked"
    assignment.refresh_from_db()
    assert assignment.remarks == "Original synthetic note"


@pytest.mark.django_db
@override_settings(ICT_OFFLINE_ENABLED=True)
def test_revocation_lock_unlock_purge_and_minimized_support_bundle(client):
    owner, incident, membership, revision, _ = offline_fixture("offline-controls")
    package, _ = create_package(client, owner, incident, revision)

    locked = client.post(
        f"/api/offline-packages/{package.id}/lock/",
        **auth_header(owner),
    )
    assert locked.status_code == 200
    assert locked.json()["status"] == "locked"
    unlocked = client.post(
        f"/api/offline-packages/{package.id}/unlock/",
        **auth_header(owner),
    )
    assert unlocked.status_code == 200
    assert unlocked.json()["status"] == "active"

    support = client.get(
        f"/api/offline-packages/{package.id}/support/",
        **auth_header(owner),
    )
    assert support.status_code == 200
    support_text = json.dumps(support.json())
    assert "Original synthetic note" not in support_text
    assert "authentication tokens" in support_text
    assert "incident payload content" in support_text

    membership.is_active = False
    membership.save()
    package_view = client.get(
        f"/api/offline-packages/{package.id}/",
        **auth_header(owner),
    )
    assert package_view.status_code == 200
    assert package_view.json()["current_status"] == "revoked"
    assert package_view.json()["payload_snapshot"] == {}
    assert AuditEvent.objects.filter(
        action="offline_package.revoked",
        target_id=str(package.id),
    ).exists()

    purged = client.post(
        f"/api/offline-packages/{package.id}/purge/",
        **auth_header(owner),
    )
    assert purged.status_code == 200
    assert purged.json()["status"] == "purged"
    assert purged.json()["payload_snapshot"] == {}
    package.refresh_from_db()
    assert package.manifest_sha256
    assert package.purged_at is not None


@pytest.mark.django_db
@override_settings(ICT_OFFLINE_ENABLED=True)
def test_receipt_and_resolution_evidence_is_append_only(client):
    owner, incident, _, revision, assignment = offline_fixture("offline-retention")
    package, device_id = create_package(client, owner, incident, revision)
    revision.status = PlanRevision.Status.APPROVED
    revision.approved_by = owner
    revision.approved_at = timezone.now()
    revision.save()
    mutation = mutation_payload(
        package=package,
        owner=owner,
        device_id=device_id,
        sequence=1,
        previous_hash=package.manifest_sha256,
        operation="assignment.delete",
        revision=revision,
        object_id=assignment.id,
        payload={},
        base_updated_at=assignment.updated_at,
    )
    assert synchronize(client, owner, package, [mutation]).status_code == 200
    receipt = OfflineMutationReceipt.objects.get()
    receipt.result = {"code": "forged"}
    with pytest.raises(RuntimeError):
        receipt.save()
    with pytest.raises(RuntimeError):
        receipt.delete()
    with pytest.raises(DjangoValidationError):
        package.delete()
