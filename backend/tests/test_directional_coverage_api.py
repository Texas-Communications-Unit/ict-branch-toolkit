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
from apps.rf_analysis.models import (
    DirectionalCoverageAnalysis,
    ElevationSnapshot,
    HAATCalculation,
    SubscriberProfile,
    SubscriberProfileVersion,
)
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


def user_with_role(username, role):
    user = get_user_model().objects.create_user(username, password="safe-test-password")
    UserRoleAssignment.objects.create(user=user, role=role)
    return user


def approved_profile_snapshot(
    *,
    owner,
    incident,
    name,
    profile_type,
    tx_frequency_hz=155_000_000,
    rx_frequency_hz=155_000_000,
    erp_w="5",
    receiver_sensitivity_dbm="-116",
    antenna_agl_m="1.5",
):
    profile = SubscriberProfile.objects.create(
        incident=incident,
        name=name,
        profile_type=profile_type,
        description="Synthetic directional-analysis fixture",
        created_by=owner,
    )
    version = SubscriberProfileVersion.objects.create(
        profile=profile,
        number=1,
        tx_frequency_hz=tx_frequency_hz,
        rx_frequency_hz=rx_frequency_hz,
        transmitter_power_w=Decimal(erp_w),
        effective_radiated_power_w=Decimal(erp_w),
        erp_source=SubscriberProfileVersion.ERPSource.ENTERED,
        receiver_sensitivity_dbm=Decimal(receiver_sensitivity_dbm),
        antenna_center_agl_m=Decimal(antenna_agl_m),
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


def directional_sources(owner, suffix="BASE", frequency_hz=155_000_000):
    incident = Incident.objects.create(
        name=f"Synthetic directional exercise {suffix}",
        incident_number=f"SYN-DIR-{suffix}",
        created_by=owner,
    )
    IncidentMembership.objects.create(
        incident=incident,
        user=owner,
        role=Role.COML,
        assigned_by=owner,
    )
    site = RadioSite.objects.create(
        incident=incident,
        name=f"Synthetic directional site {suffix}",
        latitude=Decimal("31.000000"),
        longitude=Decimal("-97.000000"),
        coordinate_format=RadioSite.CoordinateFormat.DECIMAL,
        created_by=owner,
    )
    infrastructure = approved_profile_snapshot(
        owner=owner,
        incident=incident,
        name=f"Infrastructure {suffix}",
        profile_type=SubscriberProfile.ProfileType.FIXED,
        tx_frequency_hz=frequency_hz,
        rx_frequency_hz=frequency_hz,
        erp_w="40",
        antenna_agl_m="30",
    )
    subscriber = approved_profile_snapshot(
        owner=owner,
        incident=incident,
        name=f"Portable {suffix}",
        profile_type=SubscriberProfile.ProfileType.PORTABLE,
        tx_frequency_hz=frequency_hz,
        rx_frequency_hz=frequency_hz,
        erp_w="0.001",
        antenna_agl_m="1.5",
    )
    now = timezone.now()
    elevation = ElevationSnapshot.objects.create(
        incident=incident,
        site=site,
        query_sha256="c" * 64,
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
        source_content_sha256="d" * 64,
        acquisition_state=ElevationSnapshot.AcquisitionState.COMPLETE,
        sample_snapshot=[],
        sample_sha256="e" * 64,
        retrieved_at=now,
        created_by=owner,
    )
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
        algorithm_snapshot={"method_version": "haat-radial-average-v1-provisional"},
        result_snapshot={"haat_m": "30.000"},
        result_sha256="f" * 64,
        created_by=owner,
        approved_by=owner,
        approved_at=now,
    )
    return incident, site, haat, subscriber


@pytest.mark.django_db
@override_settings(
    ICT_APPROVED_COVERAGE_CONFIGURATIONS=APPROVED_COVERAGE,
    ICT_APPROVED_DIRECTIONAL_RULES=["concentric-minimum-v1-provisional"],
)
def test_directional_lifecycle_preserves_asymmetric_paths_and_two_way_overlap(client):
    owner = user_with_role("directional-owner", Role.COML)
    incident, site, haat, subscriber = directional_sources(owner)

    status = client.get("/api/directional-analysis-status/", **auth_header(owner))
    assert status.status_code == 200
    assert status.json()["rule_version"] == "concentric-minimum-v1-provisional"
    assert status.json()["approved_for_operational_use"] is True
    assert {"cache", "gateway"}.issubset(status.json()["supported_profile_types"])

    payload = {
        "haat_calculation": str(haat.id),
        "subscriber_rf_input_snapshot": str(subscriber.id),
        "environment": "suburban",
        "preset": "balanced",
    }
    response = client.post(
        "/api/directional-coverage-analyses/",
        payload,
        content_type="application/json",
        **auth_header(owner),
    )
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["site"] == str(site.id)
    assert body["subscriber_profile_type"] == "portable"
    assert body["calculation_state"] == "complete"
    assert body["talk_out_distance_m"] > body["talk_in_distance_m"]
    assert body["probable_two_way_distance_m"] == body["talk_in_distance_m"]
    assert body["limiting_path"] == "talk_in"
    assert set(body["result_snapshot"]["geometry_wgs84"]) == {
        "talk_out",
        "talk_in",
        "probable_two_way",
    }
    assert body["result_snapshot"]["paths"]["talk_out"]["model_snapshot"]
    assert body["result_snapshot"]["paths"]["talk_in"]["model_snapshot"]
    assert body["result_sha256"]

    repeated = client.post(
        "/api/directional-coverage-analyses/",
        payload,
        content_type="application/json",
        **auth_header(owner),
    )
    assert repeated.status_code == 201
    assert repeated.json()["input_sha256"] == body["input_sha256"]
    assert repeated.json()["result_sha256"] == body["result_sha256"]

    approved = client.post(
        f"/api/directional-coverage-analyses/{body['id']}/approve/",
        **auth_header(owner),
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    analysis = DirectionalCoverageAnalysis.objects.get(pk=body["id"])
    analysis.talk_in_distance_m = 1
    with pytest.raises(DjangoValidationError, match="immutable"):
        analysis.save()
    with pytest.raises(DjangoValidationError, match="retained"):
        analysis.delete()

    event = AuditEvent.objects.filter(action="directional_coverage_analysis.created").first()
    assert event is not None
    details = str(event.details)
    assert "155000000" not in details
    assert "-116" not in details
    assert "40.000000" not in details


@pytest.mark.django_db
def test_frequency_mismatch_is_retained_without_two_way_geometry_or_approval(client):
    owner = user_with_role("directional-mismatch", Role.COML)
    incident, _, haat, _ = directional_sources(owner, "MISMATCH")
    mismatched = approved_profile_snapshot(
        owner=owner,
        incident=incident,
        name="Mismatched mobile",
        profile_type=SubscriberProfile.ProfileType.MOBILE,
        tx_frequency_hz=154_000_000,
        rx_frequency_hz=154_000_000,
        erp_w="10",
        antenna_agl_m="2",
    )
    response = client.post(
        "/api/directional-coverage-analyses/",
        {
            "haat_calculation": str(haat.id),
            "subscriber_rf_input_snapshot": str(mismatched.id),
            "environment": "rural",
            "preset": "balanced",
        },
        content_type="application/json",
        **auth_header(owner),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["calculation_state"] == "unsupported"
    assert body["probable_two_way_distance_m"] is None
    assert "probable_two_way" not in body["result_snapshot"]["geometry_wgs84"]
    assert {item["code"] for item in body["exclusions"]} == {
        "talk_out_frequency_mismatch",
        "talk_in_frequency_mismatch",
    }
    denied = client.post(
        f"/api/directional-coverage-analyses/{body['id']}/approve/",
        **auth_header(owner),
    )
    assert denied.status_code == 400


@pytest.mark.django_db
def test_reciprocal_boundary_path_is_equal_and_profile_change_creates_new_evidence(client):
    owner = user_with_role("directional-reciprocal", Role.COML)
    incident, _, haat, original_subscriber = directional_sources(
        owner,
        "BOUNDARY",
        frequency_hz=136_000_000,
    )
    reciprocal = approved_profile_snapshot(
        owner=owner,
        incident=incident,
        name="Reciprocal fixed subscriber",
        profile_type=SubscriberProfile.ProfileType.FIXED,
        tx_frequency_hz=136_000_000,
        rx_frequency_hz=136_000_000,
        erp_w="40",
        receiver_sensitivity_dbm="-116",
        antenna_agl_m="1.5",
    )

    def create(snapshot):
        return client.post(
            "/api/directional-coverage-analyses/",
            {
                "haat_calculation": str(haat.id),
                "subscriber_rf_input_snapshot": str(snapshot.id),
                "environment": "suburban",
                "preset": "balanced",
            },
            content_type="application/json",
            **auth_header(owner),
        )

    equal = create(reciprocal)
    assert equal.status_code == 201
    equal_body = equal.json()
    assert equal_body["calculation_state"] == "complete"
    assert equal_body["limiting_path"] == "equal"
    assert equal_body["talk_out_distance_m"] == equal_body["talk_in_distance_m"]
    assert equal_body["result_snapshot"]["paths"]["talk_out"]["band"] == "vhf_high"

    original = create(original_subscriber)
    assert original.status_code == 201
    changed = approved_profile_snapshot(
        owner=owner,
        incident=incident,
        name="Revised portable assumptions",
        profile_type=SubscriberProfile.ProfileType.PORTABLE,
        tx_frequency_hz=136_000_000,
        rx_frequency_hz=136_000_000,
        erp_w="0.0001",
        receiver_sensitivity_dbm="-116",
        antenna_agl_m="1.5",
    )
    revised = create(changed)
    assert revised.status_code == 201
    assert revised.json()["talk_in_distance_m"] < original.json()["talk_in_distance_m"]
    assert revised.json()["input_sha256"] != original.json()["input_sha256"]
    assert revised.json()["result_sha256"] != original.json()["result_sha256"]
    assert DirectionalCoverageAnalysis.objects.filter(
        pk=original.json()["id"],
        result_sha256=original.json()["result_sha256"],
    ).exists()


@pytest.mark.django_db
def test_directional_analysis_rejects_stale_and_cross_incident_sources_and_permissions(client):
    owner = user_with_role("directional-scope-owner", Role.COML)
    outsider = user_with_role("directional-scope-outsider", Role.COMT)
    read_only = user_with_role("directional-scope-reader", Role.READ_ONLY)
    incident, _, haat, subscriber = directional_sources(owner, "SCOPE")
    IncidentMembership.objects.create(
        incident=incident,
        user=read_only,
        role=Role.READ_ONLY,
        assigned_by=owner,
    )
    payload = {
        "haat_calculation": str(haat.id),
        "subscriber_rf_input_snapshot": str(subscriber.id),
        "environment": "open",
        "preset": "balanced",
    }
    assert (
        client.post(
            "/api/directional-coverage-analyses/",
            payload,
            content_type="application/json",
            **auth_header(read_only),
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/directional-coverage-analyses/",
            payload,
            content_type="application/json",
            **auth_header(outsider),
        ).status_code
        == 403
    )

    other_incident, _, _, other_subscriber = directional_sources(owner, "OTHER")
    assert other_incident.id != incident.id
    cross_incident = client.post(
        "/api/directional-coverage-analyses/",
        {**payload, "subscriber_rf_input_snapshot": str(other_subscriber.id)},
        content_type="application/json",
        **auth_header(owner),
    )
    assert cross_incident.status_code == 400

    type(subscriber).objects.filter(pk=subscriber.pk).update(archived_at=timezone.now())
    stale = client.post(
        "/api/directional-coverage-analyses/",
        payload,
        content_type="application/json",
        **auth_header(owner),
    )
    assert stale.status_code == 400
    assert "Archived" in str(stale.json())


@pytest.mark.django_db
@override_settings(
    ICT_APPROVED_COVERAGE_CONFIGURATIONS=APPROVED_COVERAGE,
    ICT_APPROVED_DIRECTIONAL_RULES=[],
)
def test_directional_rule_gate_fails_closed(client):
    owner = user_with_role("directional-gate", Role.COML)
    _, _, haat, subscriber = directional_sources(owner, "GATE")
    created = client.post(
        "/api/directional-coverage-analyses/",
        {
            "haat_calculation": str(haat.id),
            "subscriber_rf_input_snapshot": str(subscriber.id),
            "environment": "urban",
            "preset": "balanced",
        },
        content_type="application/json",
        **auth_header(owner),
    )
    assert created.status_code == 201
    denied = client.post(
        f"/api/directional-coverage-analyses/{created.json()['id']}/approve/",
        **auth_header(owner),
    )
    assert denied.status_code == 400
    assert "directional two-way rule" in str(denied.json())
