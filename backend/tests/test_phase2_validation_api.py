import hashlib
import json
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
from apps.plans.models import Assignment, ICS205Plan
from apps.plans.services import approve_revision
from apps.rf_analysis.calibration import (
    CALIBRATION_ALGORITHM_VERSION,
    approve_calibration_set,
    create_calibration_set,
    create_field_observation,
    review_field_observation,
)
from apps.rf_analysis.coverage import (
    approve_coverage_estimate,
    canonical_digest,
    create_coverage_estimate,
)
from apps.rf_analysis.directional import (
    DIRECTIONAL_RULE_VERSION,
    approve_directional_analysis,
    create_directional_analysis,
)
from apps.rf_analysis.models import (
    CoverageEstimate,
    ElevationSnapshot,
    FieldObservation,
    FieldObservationReview,
    HAATCalculation,
    Phase2ValidationBundle,
    SubscriberProfile,
    SubscriberProfileVersion,
)
from apps.rf_analysis.phase2_validation import VALIDATION_PROFILE_VERSION
from apps.rf_analysis.services import approve_version, create_analysis_snapshot
from apps.sites.models import RadioSite

APPROVED_COVERAGE = [
    {
        "engine": "provisional_fspl_horizon",
        "engine_version": "fspl-horizon-v1-provisional",
        "preset": "balanced",
        "preset_version": "balanced-v1-provisional",
    }
]


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


def approved_rf_snapshot(*, owner, incident, name, profile_type, power, antenna_agl):
    profile = SubscriberProfile.objects.create(
        incident=incident,
        name=name,
        profile_type=profile_type,
        description="Synthetic Phase 2 release-candidate fixture",
        created_by=owner,
    )
    version = SubscriberProfileVersion.objects.create(
        profile=profile,
        number=1,
        tx_frequency_hz=155_000_000,
        rx_frequency_hz=155_000_000,
        transmitter_power_w=Decimal(power),
        effective_radiated_power_w=Decimal(power),
        erp_source=SubscriberProfileVersion.ERPSource.ENTERED,
        receiver_sensitivity_dbm=Decimal("-116"),
        antenna_center_agl_m=Decimal(antenna_agl),
        input_basis=SubscriberProfileVersion.InputBasis.MODELED_ASSUMPTION,
        notes="Synthetic values only",
        created_by=owner,
    )
    version = approve_version(version, owner)
    return create_analysis_snapshot(
        version,
        label=f"{name} approved input",
        actor=owner,
    )


def phase2_sources(owner):
    now = timezone.now()
    incident = Incident.objects.create(
        name="Synthetic Phase 2 release-candidate exercise",
        incident_number="SYN-P2-RC-001",
        created_by=owner,
    )
    IncidentMembership.objects.create(
        incident=incident,
        user=owner,
        role=Role.COML,
        assigned_by=owner,
    )
    period = OperationalPeriod.objects.create(
        incident=incident,
        name="Synthetic operational period",
        starts_at=now,
        ends_at=now + timedelta(hours=12),
        created_by=owner,
    )
    plan = ICS205Plan.objects.create(
        incident=incident,
        operational_period=period,
        created_by=owner,
    )
    revision = plan.revisions.create(number=1, created_by=owner)
    Assignment.objects.create(
        revision=revision,
        position=1,
        function="Synthetic command",
        channel_name="SYN CALL",
        assignment="Synthetic test only",
        resource_snapshot={"type": "synthetic", "identifier": "SYN-CALL"},
        rx_frequency_hz=155_000_000,
        tx_frequency_hz=155_000_000,
        mode="analog_fm",
        remarks="Free text excluded from Phase 2 evidence.",
        contact_name="Synthetic private contact",
        site_address="Excluded synthetic address",
        phone_numbers="555-0100",
        contact_24_hour="555-0101",
    )
    revision = approve_revision(revision, owner)

    site = RadioSite.objects.create(
        incident=incident,
        name="Synthetic validation site",
        latitude=Decimal("31.000000"),
        longitude=Decimal("-97.000000"),
        coordinate_format=RadioSite.CoordinateFormat.DECIMAL,
        source_identity="Synthetic user input",
        created_by=owner,
    )
    infrastructure = approved_rf_snapshot(
        owner=owner,
        incident=incident,
        name="Synthetic infrastructure",
        profile_type=SubscriberProfile.ProfileType.FIXED,
        power="40",
        antenna_agl="30",
    )
    subscriber = approved_rf_snapshot(
        owner=owner,
        incident=incident,
        name="Synthetic portable",
        profile_type=SubscriberProfile.ProfileType.PORTABLE,
        power="1",
        antenna_agl="1.5",
    )
    elevation_query = {"schema_version": "synthetic-query-v1", "site_id": str(site.id)}
    elevation_samples = [{"azimuth": 0, "distance_m": 3000, "elevation_m": "100"}]
    elevation = ElevationSnapshot.objects.create(
        incident=incident,
        site=site,
        query_sha256=canonical_digest(elevation_query),
        query_snapshot=elevation_query,
        provider="synthetic-offline",
        dataset_product="Synthetic flat terrain",
        horizontal_crs="EPSG:4326",
        vertical_crs="SYNTHETIC:LOCAL",
        target_vertical_crs="SYNTHETIC:LOCAL",
        resolution_m=Decimal("30"),
        source_version="synthetic-v1",
        permitted_use="Synthetic tests only.",
        coverage={"type": "synthetic"},
        source_content_sha256=canonical_digest({"source": "synthetic-v1"}),
        acquisition_state=ElevationSnapshot.AcquisitionState.COMPLETE,
        sample_snapshot=elevation_samples,
        sample_sha256=canonical_digest(elevation_samples),
        transformation={"method": "none"},
        warnings=[],
        retrieved_at=now,
        stale_at=now + timedelta(days=30),
        created_by=owner,
    )
    haat_result = {
        "schema_version": "haat-result-v1",
        "haat_m": "30.000",
        "input_sha256": infrastructure.input_sha256,
        "elevation_sample_sha256": elevation.sample_sha256,
    }
    haat = HAATCalculation.objects.create(
        incident=incident,
        site=site,
        profile_version=infrastructure.profile_version,
        rf_input_snapshot=infrastructure,
        elevation_snapshot=elevation,
        status=HAATCalculation.Status.APPROVED,
        calculation_state=HAATCalculation.CalculationState.COMPLETE,
        method="general_radial_average_terrain",
        method_version="haat-radial-average-v1-provisional",
        radial_count=8,
        start_azimuth_deg=Decimal("0"),
        sampling_interval_m=1000,
        inner_distance_m=3000,
        outer_distance_m=16_000,
        rounding_m=Decimal("0.1"),
        antenna_agl_m=Decimal("30"),
        site_elevation_m=Decimal("100"),
        antenna_amsl_m=Decimal("130"),
        average_terrain_m=Decimal("100"),
        haat_m=Decimal("30"),
        sample_count=112,
        excluded_sample_count=0,
        algorithm_snapshot={
            "method_version": "haat-radial-average-v1-provisional",
            "radial_count": 8,
        },
        result_snapshot=haat_result,
        result_sha256=canonical_digest(haat_result),
        created_by=owner,
        approved_by=owner,
        approved_at=now,
    )
    coverage = create_coverage_estimate(
        haat_calculation=haat,
        environment=CoverageEstimate.Environment.SUBURBAN,
        preset="balanced",
        actor=owner,
    )
    coverage = approve_coverage_estimate(coverage, actor=owner)
    directional = create_directional_analysis(
        haat_calculation=haat,
        subscriber_rf_input_snapshot=subscriber,
        environment=CoverageEstimate.Environment.SUBURBAN,
        preset="balanced",
        actor=owner,
    )
    directional = approve_directional_analysis(directional, actor=owner)

    observations = []
    for index, (measured, predicted) in enumerate(
        (("900", "1000"), ("1000", "1000"), ("1100", "1000")),
        start=1,
    ):
        observation = create_field_observation(
            values={
                "incident": incident,
                "infrastructure_rf_input_snapshot": infrastructure,
                "subscriber_rf_input_snapshot": subscriber,
                "coverage_estimate": coverage,
                "directional_analysis": directional,
                "supersedes": None,
                "classification": FieldObservation.Classification.GOOD,
                "evidence_type": FieldObservation.EvidenceType.MEASURED,
                "observed_from": now,
                "observed_to": now,
                "location_precision": FieldObservation.LocationPrecision.GENERALIZED,
                "latitude": Decimal("31.123456"),
                "longitude": Decimal("-97.654321"),
                "location_precision_m": 1000,
                "direction_degrees": Decimal("45"),
                "path_distance_m": int(measured),
                "observer_source": "Synthetic exercise team",
                "collection_method": "scripted deterministic check",
                "environment": {"terrain": "synthetic rolling"},
                "measurements": {
                    "measured_distance_m": measured,
                    "predicted_distance_m": predicted,
                },
                "notes": "Synthetic note excluded from validation evidence.",
                "quality_flags": [],
                "source_record_id": f"SYN-{index}",
                "source_revision": "synthetic-v1",
            },
            actor=owner,
        )
        review = review_field_observation(
            observation,
            decision=FieldObservationReview.Decision.APPROVED,
            reason="Approved deterministic synthetic fixture.",
            actor=owner,
        )
        assert review.decision == FieldObservationReview.Decision.APPROVED
        observations.append(observation)
    calibration = create_calibration_set(
        incident=incident,
        name="Synthetic Phase 2 calibration",
        observations=observations,
        baseline_preset="balanced",
        baseline_preset_version="balanced-v1-provisional",
        parameters={},
        actor=owner,
    )
    calibration = approve_calibration_set(calibration, actor=owner)
    return incident, revision, haat, coverage, directional, calibration, observations


@pytest.fixture
def phase2_owner(db):
    owner = get_user_model().objects.create_user(
        "phase2-owner",
        password="safe-test-password",
    )
    UserRoleAssignment.objects.create(user=owner, role=Role.ADMINISTRATOR)
    return owner


@pytest.mark.django_db
@override_settings(
    ICT_APPROVED_COVERAGE_CONFIGURATIONS=APPROVED_COVERAGE,
    ICT_APPROVED_DIRECTIONAL_RULES=[DIRECTIONAL_RULE_VERSION],
    ICT_APPROVED_CALIBRATION_METHODS=[CALIBRATION_ALGORITHM_VERSION],
)
def test_phase2_pipeline_is_deterministic_minimized_audited_and_fail_closed(client, phase2_owner):
    status_response = client.get(
        "/api/phase2-validation-status/",
        **auth_header(phase2_owner),
    )
    assert status_response.status_code == 200
    assert status_response.json()["approved_for_release_candidate_use"] is False
    assert status_response.json()["resource_safety_limits"] == {
        "maximum_plan_assignments": 1000,
        "maximum_calibration_observations": 1000,
        "maximum_verification_upload_bytes": 10 * 1024 * 1024,
    }
    incident, revision, haat, coverage, directional, calibration, _ = phase2_sources(phase2_owner)
    payload = {
        "incident": str(incident.id),
        "approved_revision": str(revision.id),
        "haat_calculation": str(haat.id),
        "coverage_estimate": str(coverage.id),
        "directional_analysis": str(directional.id),
        "calibration_set": str(calibration.id),
    }
    queued = post_json(
        client,
        "/api/phase2-validation-bundles/",
        payload,
        phase2_owner,
    )
    assert queued.status_code == 201, queued.content
    assert queued.json()["job_state"] == "queued"
    serialized_input = json.dumps(queued.json()["input_snapshot"])
    assert "Synthetic private contact" not in serialized_input
    assert "555-0100" not in serialized_input
    assert "Free text excluded" not in serialized_input

    completed = post_json(
        client,
        f"/api/phase2-validation-bundles/{queued.json()['id']}/run/",
        {},
        phase2_owner,
    )
    assert completed.status_code == 200, completed.content
    body = completed.json()
    assert body["job_state"] == "complete"
    assert body["progress_percent"] == 100
    assert body["is_stale"] is False
    assert body["result_snapshot"]["confidence"]["level"] == "screening_only"
    comparison = body["result_snapshot"]["deterministic_observation_comparison"]
    assert comparison["counts"] == {
        "within_tolerance": 3,
        "outside_tolerance": 0,
        "not_comparable": 0,
    }
    assert "field_or_scientific_validation" in body["result_snapshot"]["unsupported_conditions"]
    serialized_result = json.dumps(body["result_snapshot"])
    assert "Synthetic exercise team" not in serialized_result
    assert "Synthetic note excluded" not in serialized_result
    assert "31.123456" not in serialized_result

    denied = post_json(
        client,
        f"/api/phase2-validation-bundles/{body['id']}/approve/",
        {},
        phase2_owner,
    )
    assert denied.status_code == 400
    with override_settings(ICT_APPROVED_PHASE2_VALIDATION_PROFILES=[VALIDATION_PROFILE_VERSION]):
        approved = post_json(
            client,
            f"/api/phase2-validation-bundles/{body['id']}/approve/",
            {},
            phase2_owner,
        )
        assert approved.status_code == 200, approved.content
        first_export = client.get(
            f"/api/phase2-validation-bundles/{body['id']}/export/",
            **auth_header(phase2_owner),
        )
        second_export = client.get(
            f"/api/phase2-validation-bundles/{body['id']}/export/",
            **auth_header(phase2_owner),
        )
    assert first_export.status_code == 200
    assert first_export.content == second_export.content
    digest = hashlib.sha256(first_export.content).hexdigest()
    assert first_export["X-Content-SHA256"] == digest
    verification = post_json(
        client,
        f"/api/phase2-validation-bundles/{body['id']}/verify/",
        {"content_sha256": digest},
        phase2_owner,
    )
    assert verification.status_code == 200
    assert verification.json()["verified"] is True
    assert AuditEvent.objects.filter(action="phase2_validation.exported").count() == 2
    audit_details = json.dumps(
        list(AuditEvent.objects.values_list("details", flat=True)),
        default=str,
    )
    assert "Synthetic private contact" not in audit_details
    assert "Synthetic exercise team" not in audit_details

    bundle = Phase2ValidationBundle.objects.get(pk=body["id"])
    bundle.result_snapshot = {"attempted": "rewrite"}
    with pytest.raises(DjangoValidationError, match="immutable"):
        bundle.save()
    with pytest.raises(DjangoValidationError, match="retained"):
        bundle.delete()


@pytest.mark.django_db
@override_settings(
    ICT_APPROVED_COVERAGE_CONFIGURATIONS=APPROVED_COVERAGE,
    ICT_APPROVED_DIRECTIONAL_RULES=[DIRECTIONAL_RULE_VERSION],
    ICT_APPROVED_CALIBRATION_METHODS=[CALIBRATION_ALGORITHM_VERSION],
    ICT_APPROVED_PHASE2_VALIDATION_PROFILES=[VALIDATION_PROFILE_VERSION],
)
def test_phase2_cancel_retry_stale_review_and_incident_permissions(client, phase2_owner):
    incident, revision, haat, coverage, directional, calibration, observations = phase2_sources(
        phase2_owner
    )
    payload = {
        "incident": str(incident.id),
        "approved_revision": str(revision.id),
        "haat_calculation": str(haat.id),
        "coverage_estimate": str(coverage.id),
        "directional_analysis": str(directional.id),
        "calibration_set": str(calibration.id),
    }
    queued = post_json(
        client,
        "/api/phase2-validation-bundles/",
        payload,
        phase2_owner,
    )
    cancelled = post_json(
        client,
        f"/api/phase2-validation-bundles/{queued.json()['id']}/cancel/",
        {},
        phase2_owner,
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["job_state"] == "cancelled"
    retried = post_json(
        client,
        f"/api/phase2-validation-bundles/{queued.json()['id']}/retry/",
        {},
        phase2_owner,
    )
    assert retried.status_code == 201, retried.content
    assert retried.json()["supersedes"] == queued.json()["id"]
    completed = post_json(
        client,
        f"/api/phase2-validation-bundles/{retried.json()['id']}/run/",
        {},
        phase2_owner,
    )
    assert completed.status_code == 200
    assert completed.json()["job_state"] == "complete"

    review_field_observation(
        observations[0],
        decision=FieldObservationReview.Decision.EXCLUDED,
        reason="Synthetic stale-evidence transition.",
        actor=phase2_owner,
    )
    detail = client.get(
        f"/api/phase2-validation-bundles/{retried.json()['id']}/",
        **auth_header(phase2_owner),
    )
    assert detail.status_code == 200
    assert detail.json()["is_stale"] is True
    assert any("review_changed" in reason for reason in detail.json()["stale_reasons"])
    approval = post_json(
        client,
        f"/api/phase2-validation-bundles/{retried.json()['id']}/approve/",
        {},
        phase2_owner,
    )
    assert approval.status_code == 400

    outsider = get_user_model().objects.create_user(
        "phase2-outsider",
        password="safe-test-password",
    )
    UserRoleAssignment.objects.create(user=outsider, role=Role.READ_ONLY)
    assert (
        client.get(
            f"/api/phase2-validation-bundles/?incident={incident.id}",
            **auth_header(outsider),
        ).json()["count"]
        == 0
    )


@pytest.mark.django_db
@override_settings(
    ICT_APPROVED_COVERAGE_CONFIGURATIONS=APPROVED_COVERAGE,
    ICT_APPROVED_DIRECTIONAL_RULES=[DIRECTIONAL_RULE_VERSION],
    ICT_APPROVED_CALIBRATION_METHODS=[CALIBRATION_ALGORITHM_VERSION],
)
def test_phase2_failed_source_check_is_retained_and_retryable(client, phase2_owner):
    incident, revision, haat, coverage, directional, calibration, _ = phase2_sources(phase2_owner)
    queued = post_json(
        client,
        "/api/phase2-validation-bundles/",
        {
            "incident": str(incident.id),
            "approved_revision": str(revision.id),
            "haat_calculation": str(haat.id),
            "coverage_estimate": str(coverage.id),
            "directional_analysis": str(directional.id),
            "calibration_set": str(calibration.id),
        },
        phase2_owner,
    )
    assert queued.status_code == 201
    ElevationSnapshot.objects.filter(pk=haat.elevation_snapshot_id).update(
        stale_at=timezone.now() - timedelta(seconds=1)
    )
    failed = post_json(
        client,
        f"/api/phase2-validation-bundles/{queued.json()['id']}/run/",
        {},
        phase2_owner,
    )
    assert failed.status_code == 200
    assert failed.json()["job_state"] == "failed"
    assert failed.json()["failure_code"] == "source_validation_failed"
    assert failed.json()["result_sha256"] == ""
    assert AuditEvent.objects.filter(action="phase2_validation.failed").exists()

    ElevationSnapshot.objects.filter(pk=haat.elevation_snapshot_id).update(
        stale_at=timezone.now() + timedelta(days=30)
    )
    retried = post_json(
        client,
        f"/api/phase2-validation-bundles/{queued.json()['id']}/retry/",
        {},
        phase2_owner,
    )
    assert retried.status_code == 201, retried.content
    completed = post_json(
        client,
        f"/api/phase2-validation-bundles/{retried.json()['id']}/run/",
        {},
        phase2_owner,
    )
    assert completed.status_code == 200
    assert completed.json()["job_state"] == "complete"
