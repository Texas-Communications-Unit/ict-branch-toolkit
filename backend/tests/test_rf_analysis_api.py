import hashlib
import json
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.authtoken.models import Token

from apps.accounts.models import Role, UserRoleAssignment
from apps.audit.models import AuditEvent
from apps.incidents.models import Incident, IncidentMembership
from apps.rf_analysis.models import RFAnalysisInputSnapshot, SubscriberProfileVersion


def auth_header(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {"HTTP_AUTHORIZATION": f"Token {token.key}"}


def user_with_role(username, role):
    user = get_user_model().objects.create_user(username, password="safe-test-password")
    UserRoleAssignment.objects.create(user=user, role=role)
    return user


def incident_for(owner, suffix):
    incident = Incident.objects.create(
        name=f"Synthetic RF Exercise {suffix}",
        incident_number=f"SYN-RF-{suffix}",
        created_by=owner,
    )
    IncidentMembership.objects.create(
        incident=incident,
        user=owner,
        role=Role.COML,
        assigned_by=owner,
    )
    return incident


def add_membership(incident, user, role, assigned_by):
    return IncidentMembership.objects.create(
        incident=incident,
        user=user,
        role=role,
        assigned_by=assigned_by,
    )


def unknown_version_payload():
    return {
        "tx_frequency_hz": None,
        "rx_frequency_hz": None,
        "tx_access_code": "",
        "rx_access_code": "",
        "transmitter_power_w": None,
        "effective_radiated_power_w": None,
        "erp_source": "unknown",
        "receiver_sensitivity_dbm": None,
        "antenna_model": None,
        "antenna_gain_db": None,
        "antenna_gain_reference": "unknown",
        "feed_line_type": None,
        "feed_line_length_m": None,
        "feed_line_loss_db": None,
        "additional_system_loss_db": None,
        "polarization": "unknown",
        "frequency_band": "unknown",
        "emission_designator": None,
        "emission_bandwidth_hz": None,
        "mounting_type": "unknown",
        "antenna_center_agl_m": None,
        "antenna_center_amsl_m": None,
        "haat_m": None,
        "input_basis": "unknown",
        "notes": None,
    }


def calculated_version_payload():
    return {
        **unknown_version_payload(),
        "tx_frequency_hz": 155_001_000,
        "rx_frequency_hz": 155_001_000,
        "tx_access_code": "NAC 293",
        "rx_access_code": "NAC 293",
        "transmitter_power_w": "10.000000",
        "erp_source": "calculated",
        "receiver_sensitivity_dbm": "-116.000",
        "antenna_model": "SYNTHETIC-ANTENNA",
        "antenna_gain_db": "2.150",
        "antenna_gain_reference": "dbi",
        "feed_line_type": "SYNTHETIC-LINE",
        "feed_line_length_m": "0.000",
        "feed_line_loss_db": "0.000",
        "additional_system_loss_db": "0.000",
        "polarization": "vertical",
        "frequency_band": "vhf_high",
        "emission_designator": "11K2F3E",
        "emission_bandwidth_hz": 11_200,
        "mounting_type": "handheld",
        "antenna_center_agl_m": "1.500",
        "antenna_center_amsl_m": "201.500",
        "haat_m": "12.000",
        "input_basis": "modeled_assumption",
        "notes": "SYNTHETIC PRIVATE RF INPUT MARKER",
    }


def create_profile(client, owner, incident, initial_version=None, name="Portable team"):
    response = client.post(
        "/api/subscriber-profiles/",
        {
            "incident": str(incident.id),
            "name": name,
            "profile_type": "portable",
            "description": "Synthetic subscriber assumptions",
            "initial_version": initial_version or unknown_version_payload(),
        },
        content_type="application/json",
        **auth_header(owner),
    )
    assert response.status_code == 201, response.content
    return response, SubscriberProfileVersion.objects.get(profile_id=response.json()["id"])


@pytest.mark.django_db
def test_profile_lifecycle_uses_nested_initial_version_and_numbered_copy(client):
    owner = user_with_role("rf-lifecycle-owner", Role.COML)
    incident = incident_for(owner, "LIFECYCLE")
    response, first = create_profile(client, owner, incident)

    body = response.json()
    assert body["incident"] == str(incident.id)
    assert body["profile_type"] == "portable"
    assert "initial_version" not in body
    assert body["versions"][0]["profile"] == body["id"]
    assert body["versions"][0]["number"] == 1
    assert body["versions"][0]["status"] == "draft"
    assert body["versions"][0]["tx_access_code"] == ""
    assert body["versions"][0]["rx_access_code"] == ""
    assert body["versions"][0]["antenna_model"] is None
    assert body["versions"][0]["erp_calculation_path"] == {"method": "unknown"}

    changed_profile = client.patch(
        f"/api/subscriber-profiles/{body['id']}/",
        {"name": "Portable team revised"},
        content_type="application/json",
        **auth_header(owner),
    )
    assert changed_profile.status_code == 200
    changed_version = client.patch(
        f"/api/subscriber-profile-versions/{first.id}/",
        {"notes": "Synthetic draft note"},
        content_type="application/json",
        **auth_header(owner),
    )
    assert changed_version.status_code == 200
    assert changed_version.json()["notes"] == "Synthetic draft note"

    approved = client.post(
        f"/api/subscriber-profile-versions/{first.id}/approve/",
        **auth_header(owner),
    )
    assert approved.status_code == 200
    copied = client.post(
        f"/api/subscriber-profile-versions/{first.id}/copy/",
        **auth_header(owner),
    )
    assert copied.status_code == 201
    assert copied.json()["profile"] == body["id"]
    assert copied.json()["number"] == 2
    assert copied.json()["status"] == "draft"
    assert copied.json()["approved_by"] is None
    assert copied.json()["input_snapshot"] == {}
    assert copied.json()["input_sha256"] == ""

    duplicate_draft = client.post(
        f"/api/subscriber-profile-versions/{first.id}/copy/",
        **auth_header(owner),
    )
    assert duplicate_draft.status_code == 400
    assert (
        client.delete(
            f"/api/subscriber-profiles/{body['id']}/",
            **auth_header(owner),
        ).status_code
        == 405
    )
    assert (
        client.put(
            f"/api/subscriber-profile-versions/{first.id}/",
            {},
            content_type="application/json",
            **auth_header(owner),
        ).status_code
        == 405
    )


@pytest.mark.django_db
def test_validation_preserves_explicit_unknowns_and_enforces_bounds_and_erp_rules(client):
    owner = user_with_role("rf-validation-owner", Role.COML)
    incident = incident_for(owner, "VALIDATION")

    unknown_response, unknown = create_profile(client, owner, incident)
    unknown_body = unknown_response.json()["versions"][0]
    assert unknown_body["tx_frequency_hz"] is None
    assert unknown_body["antenna_model"] is None
    assert unknown_body["frequency_band"] == "unknown"
    assert unknown_body["notes"] is None

    normalized_blanks = client.patch(
        f"/api/subscriber-profile-versions/{unknown.id}/",
        {
            "antenna_model": "   ",
            "feed_line_type": "",
            "emission_designator": " ",
            "notes": "",
        },
        content_type="application/json",
        **auth_header(owner),
    )
    assert normalized_blanks.status_code == 200
    assert normalized_blanks.json()["antenna_model"] is None
    assert normalized_blanks.json()["feed_line_type"] is None
    assert normalized_blanks.json()["emission_designator"] is None
    assert normalized_blanks.json()["notes"] is None

    invalid_bound = client.patch(
        f"/api/subscriber-profile-versions/{unknown.id}/",
        {"tx_frequency_hz": -1},
        content_type="application/json",
        **auth_header(owner),
    )
    assert invalid_bound.status_code == 400
    assert "tx_frequency_hz" in invalid_bound.json()

    unknown_with_value = client.patch(
        f"/api/subscriber-profile-versions/{unknown.id}/",
        {"erp_source": "unknown", "effective_radiated_power_w": "5.000000"},
        content_type="application/json",
        **auth_header(owner),
    )
    assert unknown_with_value.status_code == 400
    assert "effective_radiated_power_w" in unknown_with_value.json()

    entered_without_value = client.patch(
        f"/api/subscriber-profile-versions/{unknown.id}/",
        {"erp_source": "entered", "effective_radiated_power_w": None},
        content_type="application/json",
        **auth_header(owner),
    )
    assert entered_without_value.status_code == 400

    entered_without_context = client.patch(
        f"/api/subscriber-profile-versions/{unknown.id}/",
        {
            "erp_source": "entered",
            "effective_radiated_power_w": "5.000000",
            "notes": None,
        },
        content_type="application/json",
        **auth_header(owner),
    )
    assert entered_without_context.status_code == 400
    assert "notes" in entered_without_context.json()

    mixed_without_context = client.patch(
        f"/api/subscriber-profile-versions/{unknown.id}/",
        {"input_basis": "mixed", "notes": None},
        content_type="application/json",
        **auth_header(owner),
    )
    assert mixed_without_context.status_code == 400
    assert "notes" in mixed_without_context.json()

    calculated_without_explicit_losses = client.patch(
        f"/api/subscriber-profile-versions/{unknown.id}/",
        {
            "erp_source": "calculated",
            "transmitter_power_w": "5.000000",
            "antenna_gain_db": "0.000",
            "antenna_gain_reference": "dbd",
        },
        content_type="application/json",
        **auth_header(owner),
    )
    assert calculated_without_explicit_losses.status_code == 400
    assert "feed_line_loss_db" in calculated_without_explicit_losses.json()["erp_source"][0]


@pytest.mark.django_db
def test_calculated_erp_converts_dbi_to_dbd_and_overwrites_stale_client_value(client):
    owner = user_with_role("rf-formula-owner", Role.COML)
    incident = incident_for(owner, "FORMULA")
    _, version = create_profile(client, owner, incident, calculated_version_payload())
    version.refresh_from_db()

    assert version.effective_radiated_power_w == Decimal("10.000000")
    assert version.erp_calculation_path["method"] == "calculated"
    assert version.erp_calculation_path["method_version"] == "erp-v1-provisional"
    assert version.erp_calculation_path["components"]["dbi_to_dbd_offset_db"] == "2.150"
    assert version.erp_calculation_path["components"]["antenna_gain_dbd"] == "0.000"
    assert version.erp_calculation_path["components"]["total_loss_db"] == "0.000"
    assert version.erp_calculation_path["components"]["antenna_input_power_w"] == "10.000000"

    recalculated = client.patch(
        f"/api/subscriber-profile-versions/{version.id}/",
        {
            "effective_radiated_power_w": "999.000000",
            "antenna_gain_db": "5.150",
            "feed_line_loss_db": "1.000",
            "additional_system_loss_db": "2.000",
        },
        content_type="application/json",
        **auth_header(owner),
    )
    assert recalculated.status_code == 200, recalculated.content
    assert recalculated.json()["effective_radiated_power_w"] == "10.000000"
    assert recalculated.json()["erp_calculation_path"]["components"]["net_gain_db"] == "0.000"


@pytest.mark.django_db
def test_approval_snapshot_is_canonical_digest_stable_and_immutable(client):
    owner = user_with_role("rf-approval-owner", Role.COML)
    incident = incident_for(owner, "APPROVAL")
    profile_response, version = create_profile(
        client,
        owner,
        incident,
        calculated_version_payload(),
    )

    approved = client.post(
        f"/api/subscriber-profile-versions/{version.id}/approve/",
        **auth_header(owner),
    )
    assert approved.status_code == 200, approved.content
    body = approved.json()
    snapshot = body["input_snapshot"]
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert body["input_sha256"] == hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    assert snapshot["profile"]["id"] == profile_response.json()["id"]
    assert snapshot["profile"]["incident"] == str(incident.id)
    assert snapshot["profile_version"]["id"] == str(version.id)
    assert snapshot["profile_version"]["number"] == 1
    assert snapshot["inputs"]["transmitter_power_w"] == "10.000000"
    assert snapshot["inputs"]["antenna_center_agl_m"] == "1.500"
    assert snapshot["inputs"]["antenna_model"] == "SYNTHETIC-ANTENNA"
    assert "approved_at" not in canonical
    assert "approved_by" not in canonical

    immutable = client.patch(
        f"/api/subscriber-profile-versions/{version.id}/",
        {"notes": "Forbidden rewrite"},
        content_type="application/json",
        **auth_header(owner),
    )
    assert immutable.status_code == 400
    version.refresh_from_db()
    with pytest.raises(DjangoValidationError, match="immutable"):
        version.save()

    original_snapshot = version.input_snapshot
    original_digest = version.input_sha256
    profile_changed = client.patch(
        f"/api/subscriber-profiles/{profile_response.json()['id']}/",
        {"name": "New display name"},
        content_type="application/json",
        **auth_header(owner),
    )
    assert profile_changed.status_code == 200
    version.refresh_from_db()
    assert version.input_snapshot == original_snapshot
    assert version.input_sha256 == original_digest


@pytest.mark.django_db
def test_analysis_snapshot_requires_approval_is_immutable_and_can_be_archived(client):
    owner = user_with_role("rf-snapshot-owner", Role.COML)
    incident = incident_for(owner, "SNAPSHOT")
    _, version = create_profile(client, owner, incident, calculated_version_payload())

    rejected = client.post(
        f"/api/subscriber-profile-versions/{version.id}/create_snapshot/",
        {"label": "Synthetic analysis input"},
        content_type="application/json",
        **auth_header(owner),
    )
    assert rejected.status_code == 400

    assert (
        client.post(
            f"/api/subscriber-profile-versions/{version.id}/approve/",
            **auth_header(owner),
        ).status_code
        == 200
    )
    created = client.post(
        f"/api/subscriber-profile-versions/{version.id}/create_snapshot/",
        {"label": "Synthetic analysis input"},
        content_type="application/json",
        **auth_header(owner),
    )
    assert created.status_code == 201, created.content
    body = created.json()
    version.refresh_from_db()
    assert body["profile_version"] == str(version.id)
    assert body["incident"] == str(incident.id)
    assert body["input_snapshot"] == version.input_snapshot
    assert body["input_sha256"] == version.input_sha256
    assert body["approved_by"] == version.approved_by_id
    assert (
        client.patch(
            f"/api/rf-analysis-input-snapshots/{body['id']}/",
            {"label": "Forbidden"},
            content_type="application/json",
            **auth_header(owner),
        ).status_code
        == 405
    )
    snapshot = RFAnalysisInputSnapshot.objects.get(pk=body["id"])
    with pytest.raises(DjangoValidationError, match="immutable"):
        snapshot.save()

    archived = client.post(
        f"/api/rf-analysis-input-snapshots/{body['id']}/archive/",
        **auth_header(owner),
    )
    assert archived.status_code == 200
    assert archived.json()["archived_at"]
    assert (
        client.get(
            f"/api/rf-analysis-input-snapshots/{body['id']}/",
            **auth_header(owner),
        ).status_code
        == 404
    )


@pytest.mark.django_db
def test_material_events_record_field_names_without_rf_values(client):
    owner = user_with_role("rf-audit-owner", Role.COML)
    incident = incident_for(owner, "AUDIT")
    profile_response, version = create_profile(
        client,
        owner,
        incident,
        calculated_version_payload(),
    )
    assert (
        client.patch(
            f"/api/subscriber-profile-versions/{version.id}/",
            {"notes": "SYNTHETIC PRIVATE RF INPUT MARKER UPDATED"},
            content_type="application/json",
            **auth_header(owner),
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/subscriber-profile-versions/{version.id}/approve/",
            **auth_header(owner),
        ).status_code
        == 200
    )
    snapshot = client.post(
        f"/api/subscriber-profile-versions/{version.id}/create_snapshot/",
        {"label": "SYNTHETIC PRIVATE SNAPSHOT LABEL MARKER"},
        content_type="application/json",
        **auth_header(owner),
    )
    assert snapshot.status_code == 201
    assert (
        client.post(
            f"/api/rf-analysis-input-snapshots/{snapshot.json()['id']}/archive/",
            **auth_header(owner),
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/subscriber-profiles/{profile_response.json()['id']}/archive/",
            **auth_header(owner),
        ).status_code
        == 200
    )

    expected_actions = {
        "subscriber_profile.created",
        "subscriber_profile_version.created",
        "subscriber_profile_version.updated",
        "subscriber_profile_version.approved",
        "rf_analysis_input_snapshot.created",
        "rf_analysis_input_snapshot.archived",
        "subscriber_profile.archived",
    }
    assert expected_actions <= set(AuditEvent.objects.values_list("action", flat=True))
    serialized_details = json.dumps(list(AuditEvent.objects.values_list("details", flat=True)))
    assert "SYNTHETIC PRIVATE RF INPUT MARKER" not in serialized_details
    assert "SYNTHETIC PRIVATE SNAPSHOT LABEL MARKER" not in serialized_details
    for event in AuditEvent.objects.filter(action__in=expected_actions):
        assert set(event.details) == {"changed_fields"}
        assert all(isinstance(field, str) for field in event.details["changed_fields"])


@pytest.mark.django_db
def test_profile_archival_hides_profile_and_versions_but_retains_records(client):
    owner = user_with_role("rf-archive-owner", Role.COML)
    incident = incident_for(owner, "ARCHIVE")
    response, version = create_profile(client, owner, incident)
    profile_id = response.json()["id"]

    archived = client.post(
        f"/api/subscriber-profiles/{profile_id}/archive/",
        **auth_header(owner),
    )
    assert archived.status_code == 200
    assert archived.json()["archived_at"]
    assert (
        client.get(
            f"/api/subscriber-profiles/{profile_id}/",
            **auth_header(owner),
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/subscriber-profile-versions/{version.id}/",
            **auth_header(owner),
        ).status_code
        == 404
    )
    assert SubscriberProfileVersion.objects.filter(pk=version.id).exists()


@pytest.mark.django_db
def test_incident_scope_blocks_direct_object_access_and_cross_incident_creation(client):
    owner = user_with_role("rf-scope-owner", Role.COML)
    outsider = user_with_role("rf-scope-outsider", Role.COMT)
    incident = incident_for(owner, "SCOPE")
    response, version = create_profile(client, owner, incident)

    assert client.get("/api/subscriber-profiles/", **auth_header(outsider)).json()["count"] == 0
    assert (
        client.get(
            f"/api/subscriber-profiles/{response.json()['id']}/",
            **auth_header(outsider),
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/subscriber-profile-versions/{version.id}/",
            {"notes": "Cross-incident write"},
            content_type="application/json",
            **auth_header(outsider),
        ).status_code
        == 404
    )
    denied_create = client.post(
        "/api/subscriber-profiles/",
        {
            "incident": str(incident.id),
            "name": "Unauthorized profile",
            "profile_type": "mobile",
            "initial_version": unknown_version_payload(),
        },
        content_type="application/json",
        **auth_header(outsider),
    )
    assert denied_create.status_code == 403
    assert SubscriberProfileVersion.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("role", "can_edit", "can_approve"),
    [
        (Role.ADMINISTRATOR, True, True),
        (Role.COML, True, True),
        (Role.COMC, True, True),
        (Role.COMT, True, False),
        (Role.CONTRIBUTOR, False, False),
        (Role.READ_ONLY, False, False),
    ],
)
def test_role_policy_enforces_rf_view_edit_and_approve(
    client,
    role,
    can_edit,
    can_approve,
):
    suffix = role.replace("_", "-")
    owner = user_with_role(f"rf-policy-owner-{suffix}", Role.COML)
    incident = incident_for(owner, f"POLICY-{suffix}")
    _, version = create_profile(client, owner, incident)
    actor = user_with_role(f"rf-policy-actor-{suffix}", role)
    add_membership(incident, actor, role, owner)
    headers = auth_header(actor)

    assert (
        client.get(
            f"/api/subscriber-profile-versions/{version.id}/",
            **headers,
        ).status_code
        == 200
    )
    edit = client.patch(
        f"/api/subscriber-profile-versions/{version.id}/",
        {"notes": f"Synthetic {role} note"},
        content_type="application/json",
        **headers,
    )
    assert edit.status_code == (200 if can_edit else 403)
    approve = client.post(
        f"/api/subscriber-profile-versions/{version.id}/approve/",
        **headers,
    )
    assert approve.status_code == (200 if can_approve else 403)
