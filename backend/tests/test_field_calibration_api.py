import json
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token

from apps.accounts.models import Role, UserRoleAssignment
from apps.audit.models import AuditEvent
from apps.incidents.models import Incident, IncidentMembership
from apps.rf_analysis.calibration import CALIBRATION_ALGORITHM_VERSION
from apps.rf_analysis.models import (
    CalibrationSet,
    FieldObservation,
    FieldObservationReview,
    SubscriberProfile,
    SubscriberProfileVersion,
)
from apps.rf_analysis.services import approve_version, create_analysis_snapshot


def auth_header(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {"HTTP_AUTHORIZATION": f"Token {token.key}"}


def user_with_role(username, role):
    user = get_user_model().objects.create_user(username, password="safe-test-password")
    UserRoleAssignment.objects.create(user=user, role=role)
    return user


def approved_snapshot(owner, incident, name, profile_type):
    profile = SubscriberProfile.objects.create(
        incident=incident,
        name=name,
        profile_type=profile_type,
        description="Synthetic field-calibration fixture",
        created_by=owner,
    )
    version = SubscriberProfileVersion.objects.create(
        profile=profile,
        number=1,
        tx_frequency_hz=155_000_000,
        rx_frequency_hz=155_000_000,
        transmitter_power_w=Decimal("5"),
        effective_radiated_power_w=Decimal("5"),
        erp_source=SubscriberProfileVersion.ERPSource.ENTERED,
        receiver_sensitivity_dbm=Decimal("-116"),
        antenna_center_agl_m=Decimal("2"),
        input_basis=SubscriberProfileVersion.InputBasis.MODELED_ASSUMPTION,
        notes="Synthetic values only",
        created_by=owner,
    )
    version = approve_version(version, owner)
    return create_analysis_snapshot(version, label=f"{name} approved input", actor=owner)


def calibration_sources(owner, suffix="BASE"):
    incident = Incident.objects.create(
        name=f"Synthetic calibration exercise {suffix}",
        incident_number=f"SYN-CAL-{suffix}",
        created_by=owner,
    )
    IncidentMembership.objects.create(
        incident=incident,
        user=owner,
        role=Role.COML,
        assigned_by=owner,
    )
    infrastructure = approved_snapshot(
        owner,
        incident,
        f"Infrastructure {suffix}",
        SubscriberProfile.ProfileType.FIXED,
    )
    subscriber = approved_snapshot(
        owner,
        incident,
        f"Portable {suffix}",
        SubscriberProfile.ProfileType.PORTABLE,
    )
    return incident, infrastructure, subscriber


def observation_payload(
    incident,
    infrastructure,
    subscriber,
    *,
    measured="1000",
    predicted="1000",
    location_precision="generalized",
    supersedes=None,
    evidence_type="measured",
):
    now = timezone.now()
    measurements = {}
    if measured is not None:
        measurements["measured_distance_m"] = measured
    if predicted is not None:
        measurements["predicted_distance_m"] = predicted
    payload = {
        "incident": str(incident.id),
        "infrastructure_rf_input_snapshot": str(infrastructure.id),
        "subscriber_rf_input_snapshot": str(subscriber.id),
        "classification": "good",
        "evidence_type": evidence_type,
        "observed_from": now.isoformat(),
        "observed_to": now.isoformat(),
        "location_precision": location_precision,
        "latitude": "31.123456",
        "longitude": "-97.654321",
        "location_precision_m": 1000,
        "direction_degrees": "45.000",
        "path_distance_m": 1000,
        "observer_source": "Synthetic exercise team",
        "collection_method": "scripted field check",
        "environment": {"terrain": "synthetic rolling", "weather": "synthetic clear"},
        "measurements": measurements,
        "notes": "Synthetic observation; no operational details.",
        "quality_flags": [],
        "source_record_id": "",
        "source_revision": "synthetic-observation-v1",
    }
    if supersedes:
        payload["supersedes"] = str(supersedes.id)
    return payload


def post_json(client, path, payload, user):
    return client.post(
        path,
        data=json.dumps(payload),
        content_type="application/json",
        **auth_header(user),
    )


def create_and_approve_observation(
    client,
    owner,
    incident,
    infrastructure,
    subscriber,
    *,
    measured,
    predicted,
):
    response = post_json(
        client,
        "/api/field-observations/",
        observation_payload(
            incident,
            infrastructure,
            subscriber,
            measured=measured,
            predicted=predicted,
        ),
        owner,
    )
    assert response.status_code == 201, response.content
    review = post_json(
        client,
        f"/api/field-observations/{response.json()['id']}/review/",
        {"decision": "approved", "reason": "Approved synthetic calibration fixture."},
        owner,
    )
    assert review.status_code == 200, review.content
    return FieldObservation.objects.get(pk=response.json()["id"])


@pytest.mark.django_db
def test_observation_generalizes_before_storage_and_retains_review_history(client):
    owner = user_with_role("calibration-owner", Role.ADMINISTRATOR)
    incident, infrastructure, subscriber = calibration_sources(owner)
    response = post_json(
        client,
        "/api/field-observations/",
        observation_payload(incident, infrastructure, subscriber),
        owner,
    )
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["latitude"] != "31.123456"
    assert body["longitude"] != "-97.654321"
    assert body["location_precision"] == "generalized"
    assert body["input_snapshot"]["location"] == {
        "precision": "generalized",
        "coordinate_reference": "EPSG:4326",
        "latitude": body["latitude"],
        "longitude": body["longitude"],
        "precision_m": 1000,
        "raw_coordinates_retained": False,
    }
    observation = FieldObservation.objects.get(pk=body["id"])
    assert "31.123456" not in json.dumps(observation.input_snapshot)
    audit = AuditEvent.objects.get(action="field_observation.created")
    assert "31.123456" not in json.dumps(audit.details)
    assert "Synthetic observation" not in json.dumps(audit.details)

    approved = post_json(
        client,
        f"/api/field-observations/{observation.id}/review/",
        {"decision": "approved", "reason": "Synthetic evidence is complete."},
        owner,
    )
    assert approved.status_code == 200
    assert approved.json()["current_review_state"] == "approved"
    excluded = post_json(
        client,
        f"/api/field-observations/{observation.id}/review/",
        {"decision": "excluded", "reason": "Exercise operator marked it for exclusion."},
        owner,
    )
    assert excluded.status_code == 200
    assert excluded.json()["current_review_state"] == "excluded"
    assert FieldObservationReview.objects.filter(observation=observation).count() == 2

    observation.notes = "Attempted rewrite"
    with pytest.raises(DjangoValidationError):
        observation.save()
    with pytest.raises(DjangoValidationError):
        observation.delete()
    review = observation.reviews.first()
    review.reason = "Attempted rewrite"
    with pytest.raises(DjangoValidationError):
        review.save()


@pytest.mark.django_db
def test_redaction_correction_and_source_validation_fail_closed(client):
    owner = user_with_role("calibration-validation", Role.ADMINISTRATOR)
    incident, infrastructure, subscriber = calibration_sources(owner, "VALIDATE")
    redacted_payload = observation_payload(
        incident,
        infrastructure,
        subscriber,
        location_precision="redacted",
    )
    response = post_json(client, "/api/field-observations/", redacted_payload, owner)
    assert response.status_code == 201
    assert response.json()["latitude"] is None
    assert response.json()["longitude"] is None
    assert response.json()["location_precision_m"] is None
    original = FieldObservation.objects.get(pk=response.json()["id"])

    correction = post_json(
        client,
        "/api/field-observations/",
        observation_payload(
            incident,
            infrastructure,
            subscriber,
            location_precision="exact",
            supersedes=original,
        ),
        owner,
    )
    assert correction.status_code == 201, correction.content
    original.refresh_from_db()
    assert str(original.superseded_by.id) == correction.json()["id"]
    rejected_review = post_json(
        client,
        f"/api/field-observations/{original.id}/review/",
        {"decision": "approved", "reason": "Should be rejected because it is superseded."},
        owner,
    )
    assert rejected_review.status_code == 400

    imported = observation_payload(
        incident,
        infrastructure,
        subscriber,
        evidence_type="imported",
    )
    assert post_json(client, "/api/field-observations/", imported, owner).status_code == 400
    modeled = observation_payload(
        incident,
        infrastructure,
        subscriber,
        evidence_type="modeled",
    )
    assert post_json(client, "/api/field-observations/", modeled, owner).status_code == 400

    other_incident, _, other_subscriber = calibration_sources(owner, "OTHER")
    cross_incident = observation_payload(
        incident,
        infrastructure,
        other_subscriber,
    )
    assert post_json(client, "/api/field-observations/", cross_incident, owner).status_code == 400
    assert other_incident.id != incident.id


@pytest.mark.django_db
def test_calibration_is_deterministic_transparent_and_fail_closed(client):
    owner = user_with_role("calibration-fit", Role.ADMINISTRATOR)
    incident, infrastructure, subscriber = calibration_sources(owner, "FIT")
    observations = [
        create_and_approve_observation(
            client,
            owner,
            incident,
            infrastructure,
            subscriber,
            measured=measured,
            predicted=predicted,
        )
        for measured, predicted in [
            ("1000", "1000"),
            ("1200", "1000"),
            ("800", "1000"),
            (None, "1000"),
            ("1000", "100"),
        ]
    ]
    payload = {
        "incident": str(incident.id),
        "name": "Synthetic portable calibration",
        "observations": [str(observation.id) for observation in observations],
        "baseline_preset": "balanced",
        "baseline_preset_version": "balanced-v1-provisional",
        "parameters": {
            "minimum_samples": 3,
            "minimum_ratio": "0.25",
            "maximum_ratio": "4",
        },
    }
    response = post_json(client, "/api/calibration-sets/", payload, owner)
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["version"] == 1
    assert body["calculation_state"] == "complete"
    assert body["recommended_preset"] == {
        "schema_version": "incident-local-calibration-recommendation-v1",
        "base_preset": "balanced",
        "base_preset_version": "balanced-v1-provisional",
        "distance_multiplier": "1.000",
        "scope": "incident_local",
        "promotion_state": "not_promoted",
        "organization_default_overwritten": False,
    }
    assert body["before_after"]["before"] is not None
    assert body["before_after"]["after"] is not None
    assert len(body["exclusions"]) == 2
    serialized_result = json.dumps(body["result_snapshot"])
    assert "observer_source" not in serialized_result
    assert "notes" not in serialized_result
    assert "latitude" not in serialized_result

    approval_path = f"/api/calibration-sets/{body['id']}/approve/"
    assert post_json(client, approval_path, {}, owner).status_code == 400
    excluded = post_json(
        client,
        f"/api/field-observations/{observations[0].id}/review/",
        {"decision": "excluded", "reason": "Changed after the calibration snapshot."},
        owner,
    )
    assert excluded.status_code == 200
    with override_settings(ICT_APPROVED_CALIBRATION_METHODS=[CALIBRATION_ALGORITHM_VERSION]):
        stale_approval = post_json(client, approval_path, {}, owner)
    assert stale_approval.status_code == 400

    reapproved = post_json(
        client,
        f"/api/field-observations/{observations[0].id}/review/",
        {"decision": "approved", "reason": "Re-approved with new review evidence."},
        owner,
    )
    assert reapproved.status_code == 200
    replacement = post_json(client, "/api/calibration-sets/", payload, owner)
    assert replacement.status_code == 201
    assert replacement.json()["version"] == 2
    with override_settings(ICT_APPROVED_CALIBRATION_METHODS=[CALIBRATION_ALGORITHM_VERSION]):
        approved = post_json(
            client,
            f"/api/calibration-sets/{replacement.json()['id']}/approve/",
            {},
            owner,
        )
    assert approved.status_code == 200, approved.content
    assert approved.json()["status"] == "approved"
    assert approved.json()["is_locked"] is True
    calibration_set = CalibrationSet.objects.get(pk=replacement.json()["id"])
    calibration_set.name = "Attempted rewrite"
    with pytest.raises(DjangoValidationError):
        calibration_set.save()
    with pytest.raises(DjangoValidationError):
        calibration_set.delete()


@pytest.mark.django_db
def test_insufficient_calibration_and_incident_permissions(client):
    owner = user_with_role("calibration-permissions", Role.ADMINISTRATOR)
    reader = user_with_role("calibration-reader", Role.READ_ONLY)
    incident, infrastructure, subscriber = calibration_sources(owner, "PERMISSIONS")
    IncidentMembership.objects.create(
        incident=incident,
        user=reader,
        role=Role.READ_ONLY,
        assigned_by=owner,
    )
    observations = [
        create_and_approve_observation(
            client,
            owner,
            incident,
            infrastructure,
            subscriber,
            measured=value,
            predicted="1000",
        )
        for value in ("900", "1100")
    ]
    payload = {
        "incident": str(incident.id),
        "name": "Insufficient synthetic set",
        "observations": [str(observation.id) for observation in observations],
        "baseline_preset": "balanced",
        "baseline_preset_version": "balanced-v1-provisional",
        "parameters": {},
    }
    response = post_json(client, "/api/calibration-sets/", payload, owner)
    assert response.status_code == 201
    assert response.json()["calculation_state"] == "insufficient_data"
    assert response.json()["recommended_preset"]["distance_multiplier"] is None
    with override_settings(ICT_APPROVED_CALIBRATION_METHODS=[CALIBRATION_ALGORITHM_VERSION]):
        approval = post_json(
            client,
            f"/api/calibration-sets/{response.json()['id']}/approve/",
            {},
            owner,
        )
    assert approval.status_code == 400

    denied_observation = post_json(
        client,
        "/api/field-observations/",
        observation_payload(incident, infrastructure, subscriber),
        reader,
    )
    assert denied_observation.status_code == 403
    denied_calibration = post_json(client, "/api/calibration-sets/", payload, reader)
    assert denied_calibration.status_code == 403
