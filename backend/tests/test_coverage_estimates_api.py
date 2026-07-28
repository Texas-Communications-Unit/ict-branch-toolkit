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
from apps.rf_analysis.coverage import EstimateRequest, ProvisionalFsplHorizonEngine
from apps.rf_analysis.models import (
    CoverageEstimate,
    ElevationSnapshot,
    HAATCalculation,
    SubscriberProfile,
    SubscriberProfileVersion,
)
from apps.rf_analysis.services import approve_version, create_analysis_snapshot
from apps.sites.models import RadioSite


def auth_header(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {"HTTP_AUTHORIZATION": f"Token {token.key}"}


def user_with_role(username, role):
    user = get_user_model().objects.create_user(username, password="safe-test-password")
    UserRoleAssignment.objects.create(user=user, role=role)
    return user


def incident_for(owner, suffix):
    incident = Incident.objects.create(
        name=f"Synthetic coverage exercise {suffix}",
        incident_number=f"SYN-COVERAGE-{suffix}",
        created_by=owner,
    )
    IncidentMembership.objects.create(
        incident=incident,
        user=owner,
        role=Role.COML,
        assigned_by=owner,
    )
    return incident


def approved_sources(owner, incident, suffix="BASE", frequency_hz=155_000_000):
    site = RadioSite.objects.create(
        incident=incident,
        name=f"Synthetic coverage site {suffix}",
        latitude=Decimal("31.000000"),
        longitude=Decimal("-97.000000"),
        coordinate_format=RadioSite.CoordinateFormat.DECIMAL,
        created_by=owner,
    )
    profile = SubscriberProfile.objects.create(
        incident=incident,
        name=f"Synthetic coverage profile {suffix}",
        profile_type=SubscriberProfile.ProfileType.FIXED,
        description="Synthetic coverage-estimate fixture only",
        created_by=owner,
    )
    version = SubscriberProfileVersion.objects.create(
        profile=profile,
        number=1,
        tx_frequency_hz=frequency_hz,
        rx_frequency_hz=frequency_hz,
        transmitter_power_w=Decimal("50"),
        effective_radiated_power_w=Decimal("40"),
        erp_source=SubscriberProfileVersion.ERPSource.ENTERED,
        receiver_sensitivity_dbm=Decimal("-116"),
        antenna_center_agl_m=Decimal("30"),
        input_basis=SubscriberProfileVersion.InputBasis.MODELED_ASSUMPTION,
        notes="Synthetic values only",
        created_by=owner,
    )
    version = approve_version(version, owner)
    rf_snapshot = create_analysis_snapshot(
        version,
        label=f"Synthetic approved coverage input {suffix}",
        actor=owner,
    )
    now = timezone.now()
    elevation = ElevationSnapshot.objects.create(
        incident=incident,
        site=site,
        query_sha256=f"{suffix.lower():0<64}"[:64],
        query_snapshot={"schema_version": "synthetic-query-v1"},
        provider="synthetic-offline",
        dataset_product="Synthetic flat terrain",
        horizontal_crs="EPSG:4326",
        vertical_crs="SYNTHETIC:LOCAL",
        target_vertical_crs="SYNTHETIC:LOCAL",
        resolution_m=Decimal("30"),
        source_version="synthetic-v1",
        permitted_use="Synthetic tests only.",
        coverage={"type": "synthetic"},
        source_content_sha256=f"{suffix.upper():0<64}"[:64],
        acquisition_state=ElevationSnapshot.AcquisitionState.COMPLETE,
        sample_snapshot=[],
        sample_sha256="a" * 64,
        retrieved_at=now,
        created_by=owner,
    )
    haat = HAATCalculation.objects.create(
        incident=incident,
        site=site,
        profile_version=version,
        rf_input_snapshot=rf_snapshot,
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
        algorithm_snapshot={"method_version": "haat-radial-average-v1-provisional"},
        result_snapshot={"haat_m": "30.000"},
        result_sha256="b" * 64,
        created_by=owner,
        approved_by=owner,
        approved_at=now,
    )
    return site, rf_snapshot, haat


@pytest.mark.django_db
@override_settings(
    ICT_APPROVED_COVERAGE_CONFIGURATIONS=[
        {
            "engine": "provisional_fspl_horizon",
            "engine_version": "fspl-horizon-v1-provisional",
            "preset": "balanced",
            "preset_version": "balanced-v1-provisional",
        }
    ]
)
def test_estimate_lifecycle_is_explainable_deterministic_and_immutable(client):
    owner = user_with_role("coverage-owner", Role.COML)
    incident = incident_for(owner, "LIFECYCLE")
    site, rf_snapshot, haat = approved_sources(owner, incident)

    engine_status = client.get("/api/coverage-engine/", **auth_header(owner))
    assert engine_status.status_code == 200
    assert engine_status.json()["engine_version"] == "fspl-horizon-v1-provisional"
    assert engine_status.json()["approved_for_operational_use"] is True
    assert engine_status.json()["approved_presets"] == [
        {
            "preset": "balanced",
            "preset_version": "balanced-v1-provisional",
        }
    ]
    assert engine_status.json()["presets"]["balanced"]["version"]

    payload = {
        "haat_calculation": str(haat.id),
        "environment": "suburban",
        "preset": "balanced",
    }
    response = client.post(
        "/api/coverage-estimates/",
        payload,
        content_type="application/json",
        **auth_header(owner),
    )
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["calculation_state"] == "complete"
    assert body["status"] == "draft"
    assert body["band"] == "vhf_high"
    assert body["site"] == str(site.id)
    assert body["rf_input_snapshot"] == str(rf_snapshot.id)
    assert body["haat_calculation"] == str(haat.id)
    assert 0 < body["conservative_distance_m"] <= body["nominal_distance_m"]
    assert body["nominal_distance_m"] <= body["optimistic_distance_m"]
    assert body["result_snapshot"]["geometry_wgs84"]["nominal"]["type"] == "Polygon"
    assert len(body["result_snapshot"]["geometry_wgs84"]["nominal"]["coordinates"][0]) == 73
    assert body["model_snapshot"]["formulae"]["free_space_path_loss"]
    assert body["model_snapshot"]["intermediate_values"]["limiting_factors"]
    assert "planning estimate only" in body["explanation"].lower()
    assert body["input_sha256"]
    assert body["result_sha256"]

    repeated = client.post(
        "/api/coverage-estimates/",
        payload,
        content_type="application/json",
        **auth_header(owner),
    )
    assert repeated.status_code == 201
    assert repeated.json()["input_sha256"] == body["input_sha256"]
    assert repeated.json()["result_sha256"] == body["result_sha256"]

    approved = client.post(
        f"/api/coverage-estimates/{body['id']}/approve/",
        **auth_header(owner),
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["is_locked"] is True

    estimate = CoverageEstimate.objects.get(pk=body["id"])
    estimate.nominal_distance_m = 1
    with pytest.raises(DjangoValidationError, match="immutable"):
        estimate.save()
    with pytest.raises(DjangoValidationError, match="retained"):
        estimate.delete()

    created_event = AuditEvent.objects.filter(action="coverage_estimate.created").first()
    assert created_event is not None
    serialized_details = str(created_event.details)
    assert "155000000" not in serialized_details
    assert "-116" not in serialized_details
    assert "40.000000" not in serialized_details


@pytest.mark.django_db
def test_environment_changes_result_and_unsupported_frequency_is_preserved(client):
    owner = user_with_role("coverage-environment", Role.COML)
    incident = incident_for(owner, "ENVIRONMENT")
    _, _, supported_haat = approved_sources(owner, incident, "SUPPORTED")
    _, _, unsupported_haat = approved_sources(
        owner,
        incident,
        "UNSUPPORTED",
        frequency_hz=120_000_000,
    )

    def create(haat, environment):
        return client.post(
            "/api/coverage-estimates/",
            {
                "haat_calculation": str(haat.id),
                "environment": environment,
                "preset": "balanced",
            },
            content_type="application/json",
            **auth_header(owner),
        )

    open_result = create(supported_haat, "open")
    urban_result = create(supported_haat, "dense_urban")
    assert open_result.status_code == 201
    assert urban_result.status_code == 201
    assert open_result.json()["nominal_distance_m"] >= urban_result.json()["nominal_distance_m"]
    unapproved_configuration = client.post(
        f"/api/coverage-estimates/{open_result.json()['id']}/approve/",
        **auth_header(owner),
    )
    assert unapproved_configuration.status_code == 400
    assert "qualified-practitioner approval gate" in str(unapproved_configuration.json())

    unsupported = create(unsupported_haat, "open")
    assert unsupported.status_code == 201
    assert unsupported.json()["calculation_state"] == "unsupported"
    assert unsupported.json()["nominal_distance_m"] is None
    assert unsupported.json()["result_snapshot"]["geometry_wgs84"] == {}
    assert unsupported.json()["exclusions"][0]["code"] == "unsupported_input"
    denied_approval = client.post(
        f"/api/coverage-estimates/{unsupported.json()['id']}/approve/",
        **auth_header(owner),
    )
    assert denied_approval.status_code == 400


@pytest.mark.django_db
def test_estimates_require_approved_complete_haat_and_incident_permission(client):
    owner = user_with_role("coverage-scope-owner", Role.COML)
    outsider = user_with_role("coverage-scope-outsider", Role.COMT)
    read_only = user_with_role("coverage-read-only", Role.READ_ONLY)
    incident = incident_for(owner, "SCOPE")
    _, _, haat = approved_sources(owner, incident)
    IncidentMembership.objects.create(
        incident=incident,
        user=read_only,
        role=Role.READ_ONLY,
        assigned_by=owner,
    )

    payload = {
        "haat_calculation": str(haat.id),
        "environment": "rural",
        "preset": "balanced",
    }
    forbidden = client.post(
        "/api/coverage-estimates/",
        payload,
        content_type="application/json",
        **auth_header(read_only),
    )
    assert forbidden.status_code == 403
    outsider_create = client.post(
        "/api/coverage-estimates/",
        payload,
        content_type="application/json",
        **auth_header(outsider),
    )
    assert outsider_create.status_code == 403

    HAATCalculation.objects.filter(pk=haat.pk).update(
        status=HAATCalculation.Status.DRAFT,
        approved_by=None,
        approved_at=None,
    )
    not_approved = client.post(
        "/api/coverage-estimates/",
        payload,
        content_type="application/json",
        **auth_header(owner),
    )
    assert not_approved.status_code == 400
    assert "Approve and lock" in str(not_approved.json())


@pytest.mark.parametrize(
    ("frequency_hz", "expected_band"),
    [
        (30_000_000, "vhf_low"),
        (88_000_000, "vhf_low"),
        (136_000_000, "vhf_high"),
        (174_000_000, "vhf_high"),
        (380_000_000, "uhf"),
        (520_000_000, "uhf"),
        (698_000_000, "700_mhz"),
        (806_000_000, "700_mhz"),
        (806_000_001, "800_mhz"),
        (869_000_000, "800_mhz"),
        (896_000_000, "900_mhz"),
        (941_000_000, "900_mhz"),
    ],
)
def test_engine_band_boundaries_and_unit_conversion(frequency_hz, expected_band):
    result = ProvisionalFsplHorizonEngine().calculate(
        EstimateRequest(
            frequency_hz=frequency_hz,
            effective_radiated_power_w=Decimal("40"),
            receiver_sensitivity_dbm=Decimal("-116"),
            haat_m=Decimal("30"),
            environment=CoverageEstimate.Environment.SUBURBAN,
            preset_name="balanced",
        )
    )
    assert result.calculation_state == CoverageEstimate.CalculationState.COMPLETE
    assert result.band == expected_band
    assert result.model_snapshot["intermediate_values"]["frequency_mhz"] == format(
        Decimal(frequency_hz) / Decimal(1_000_000),
        "f",
    )
