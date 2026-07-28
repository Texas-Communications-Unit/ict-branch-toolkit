import json
import time
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
from apps.rf_analysis.coverage import canonical_digest
from apps.rf_analysis.models import (
    CoverageEstimate,
    ElevationSnapshot,
    HAATCalculation,
    SubscriberProfile,
    SubscriberProfileVersion,
    TerrainAnalysis,
)
from apps.rf_analysis.services import approve_version, create_analysis_snapshot
from apps.rf_analysis.terrain import (
    TERRAIN_ENGINE_ID,
    TERRAIN_ENGINE_VERSION,
    TERRAIN_PROVIDER_VERSION,
    SyntheticTerrainProfileProvider,
    _destination_point,
)
from apps.sites.models import RadioSite

TERRAIN_PROVIDER = "apps.rf_analysis.terrain.SyntheticTerrainProfileProvider"
TERRAIN_ENGINE = "apps.rf_analysis.terrain.ProvisionalSampledLineOfSightEngine"
SYNTHETIC_SOURCE_DESCRIPTOR = {
    "provider": "synthetic-offline",
    "provider_version": TERRAIN_PROVIDER_VERSION,
    "dataset_product": "ICT Toolkit deterministic terrain profile fixture",
    "dataset_version": "synthetic-terrain-profile-v1",
}
SYNTHETIC_TERRAIN_APPROVAL = [
    {
        **SYNTHETIC_SOURCE_DESCRIPTOR,
        "source_content_sha256": canonical_digest(SYNTHETIC_SOURCE_DESCRIPTOR),
        "engine": TERRAIN_ENGINE_ID,
        "engine_version": TERRAIN_ENGINE_VERSION,
    }
]


def test_destination_point_normalizes_longitude_at_dateline():
    _, longitude = _destination_point(
        latitude=Decimal("0"),
        longitude=Decimal("179.900000"),
        azimuth_deg=Decimal("90"),
        distance_m=200_000,
    )
    assert Decimal("-180") <= Decimal(longitude) <= Decimal("180")
    assert Decimal(longitude) < 0


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


def user_with_role(username, role):
    user = get_user_model().objects.create_user(username, password="safe-test-password")
    UserRoleAssignment.objects.create(user=user, role=role)
    return user


def approved_coverage(owner, suffix="BASE"):
    incident = Incident.objects.create(
        name=f"Synthetic terrain exercise {suffix}",
        incident_number=f"SYN-TERRAIN-{suffix}",
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
        name=f"Synthetic terrain site {suffix}",
        latitude=Decimal("31.000000"),
        longitude=Decimal("-97.000000"),
        coordinate_format=RadioSite.CoordinateFormat.DECIMAL,
        source_identity="Synthetic user input",
        created_by=owner,
    )
    profile = SubscriberProfile.objects.create(
        incident=incident,
        name=f"Synthetic terrain transmitter {suffix}",
        profile_type=SubscriberProfile.ProfileType.FIXED,
        description="Synthetic P3.1 fixture only",
        created_by=owner,
    )
    version = SubscriberProfileVersion.objects.create(
        profile=profile,
        number=1,
        tx_frequency_hz=155_000_000,
        rx_frequency_hz=155_000_000,
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
        label=f"Synthetic terrain RF input {suffix}",
        actor=owner,
    )
    now = timezone.now()
    elevation = ElevationSnapshot.objects.create(
        incident=incident,
        site=site,
        query_sha256=canonical_digest({"site_id": str(site.id), "fixture": suffix}),
        query_snapshot={"site_id": str(site.id), "fixture": suffix},
        provider="synthetic-offline",
        dataset_product="Synthetic flat HAAT terrain",
        horizontal_crs="EPSG:4326",
        vertical_crs="SYNTHETIC:LOCAL",
        target_vertical_crs="SYNTHETIC:LOCAL",
        resolution_m=Decimal("30"),
        source_version="synthetic-haat-v1",
        permitted_use="Synthetic tests only.",
        coverage={"type": "synthetic"},
        source_content_sha256=canonical_digest({"source": "synthetic-haat-v1"}),
        acquisition_state=ElevationSnapshot.AcquisitionState.COMPLETE,
        sample_snapshot=[{"distance_m": 3000, "elevation_m": "100.000"}],
        sample_sha256=canonical_digest([{"distance_m": 3000, "elevation_m": "100.000"}]),
        transformation={"method": "identity"},
        warnings=[],
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
        result_sha256=canonical_digest({"haat_m": "30.000", "fixture": suffix}),
        created_by=owner,
        approved_by=owner,
        approved_at=now,
    )
    coverage = CoverageEstimate.objects.create(
        incident=incident,
        site=site,
        rf_input_snapshot=rf_snapshot,
        haat_calculation=haat,
        status=CoverageEstimate.Status.APPROVED,
        calculation_state=CoverageEstimate.CalculationState.COMPLETE,
        environment=CoverageEstimate.Environment.SUBURBAN,
        band="vhf_high",
        engine="provisional_fspl_horizon",
        engine_version="fspl-horizon-v1-provisional",
        preset="balanced",
        preset_version="balanced-v1-provisional",
        center_latitude=site.latitude,
        center_longitude=site.longitude,
        nominal_distance_m=10_000,
        conservative_distance_m=8_000,
        optimistic_distance_m=12_000,
        input_snapshot={"fixture": suffix},
        input_sha256=canonical_digest({"coverage_input": suffix}),
        model_snapshot={"tested_limits": {"maximum_distance_m": 200_000}},
        warnings=["Synthetic fixture."],
        exclusions=[],
        explanation="Synthetic Phase 2 estimate for terrain comparison.",
        result_snapshot={"nominal_distance_m": 10_000},
        result_sha256=canonical_digest({"coverage_result": suffix}),
        created_by=owner,
        approved_by=owner,
        approved_at=now,
    )
    return incident, site, coverage


def terrain_payload(coverage, **overrides):
    return {
        "coverage_estimate": str(coverage.id),
        "azimuth_deg": "90.000",
        "maximum_distance_m": 10_000,
        "sample_interval_m": 1_000,
        "receiver_height_m": "1.500",
        "clearance_m": "1.000",
        **overrides,
    }


@pytest.mark.django_db
@override_settings(
    ICT_TERRAIN_PROVIDER=TERRAIN_PROVIDER,
    ICT_TERRAIN_ENGINE=TERRAIN_ENGINE,
    ICT_APPROVED_TERRAIN_CONFIGURATIONS=SYNTHETIC_TERRAIN_APPROVAL,
    ICT_SYNTHETIC_TERRAIN_MODE="flat",
)
def test_terrain_lifecycle_is_source_aware_deterministic_and_immutable(client):
    owner = user_with_role("terrain-owner", Role.COML)
    incident, site, coverage = approved_coverage(owner, "LIFECYCLE")

    status_response = client.get("/api/terrain-analysis-status/", **auth_header(owner))
    assert status_response.status_code == 200
    status_body = status_response.json()
    assert status_body["available"] is True
    assert status_body["provider"]["provider"] == "synthetic-offline"
    assert status_body["provider"]["horizontal_crs"] == "EPSG:4326"
    assert status_body["provider"]["target_vertical_crs"] == "SYNTHETIC:LOCAL"
    assert status_body["provider"]["resolution_m"] == "30.000"
    assert status_body["engine"]["capabilities"]["sampled_line_of_sight"] is True
    assert status_body["engine"]["capabilities"]["diffraction"] is False

    queued = post_json(
        client,
        "/api/terrain-analyses/",
        terrain_payload(coverage),
        owner,
    )
    assert queued.status_code == 201, queued.content
    queued_body = queued.json()
    assert queued_body["incident"] == str(incident.id)
    assert queued_body["site"] == str(site.id)
    assert queued_body["job_state"] == "queued"
    assert queued_body["progress_percent"] == 0
    assert queued_body["input_snapshot"]["terrain_source"]["dataset_version"]
    assert queued_body["input_snapshot"]["phase2_coverage_estimate"]["result_sha256"]
    assert (
        queued_body["input_snapshot"]["path_generation"]["method_version"]
        == "spherical-destination-mean-earth-radius-v1"
    )

    completed = client.post(
        f"/api/terrain-analyses/{queued_body['id']}/run/",
        **auth_header(owner),
    )
    assert completed.status_code == 200
    body = completed.json()
    assert body["job_state"] == "complete"
    assert body["analysis_state"] == "complete"
    assert body["progress_percent"] == 100
    assert body["result_snapshot"]["profile"]["sample_count"] == 11
    assert body["result_snapshot"]["profile"]["sample_sha256"]
    assert body["result_snapshot"]["line_of_sight"]["continuous_clear_distance_m"] == 10_000
    comparison = body["result_snapshot"]["comparison"]
    assert comparison["phase2_nominal_distance_m"] == 10_000
    assert comparison["terrain_continuous_los_distance_m"] == 10_000
    assert comparison["layer_behavior"].startswith("Terrain evidence is a separate")
    assert body["result_snapshot"]["source"]["transformation"]["method"] == "identity"
    assert "not diffraction modeling" in body["result_snapshot"]["disclaimer"].lower()

    repeated = post_json(
        client,
        "/api/terrain-analyses/",
        terrain_payload(coverage),
        owner,
    )
    repeated_run = client.post(
        f"/api/terrain-analyses/{repeated.json()['id']}/run/",
        **auth_header(owner),
    )
    assert repeated_run.status_code == 200
    assert (
        repeated_run.json()["result_snapshot"]["profile"]["sample_sha256"]
        == body["result_snapshot"]["profile"]["sample_sha256"]
    )

    approved = client.post(
        f"/api/terrain-analyses/{body['id']}/approve/",
        **auth_header(owner),
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["is_locked"] is True

    analysis = TerrainAnalysis.objects.get(pk=body["id"])
    analysis.maximum_distance_m = 1
    with pytest.raises(DjangoValidationError, match="immutable"):
        analysis.save()
    with pytest.raises(DjangoValidationError, match="retained"):
        analysis.delete()

    terrain_events = AuditEvent.objects.filter(action__startswith="terrain_analysis.")
    assert {
        "terrain_analysis.queued",
        "terrain_analysis.completed",
        "terrain_analysis.approved",
    }.issubset(set(terrain_events.values_list("action", flat=True)))
    audit_details = json.dumps([event.details for event in terrain_events])
    assert "31.000000" not in audit_details
    assert "-97.000000" not in audit_details
    assert "terrain_elevation_m" not in audit_details
    assert "source_elevation_m" not in audit_details


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("mode", "expected_state", "expected_edge", "expected_gaps"),
    [
        ("ridge", "complete", False, 0),
        ("valley", "complete", False, 0),
        ("missing", "partial", False, 2),
        ("boundary", "partial", True, 3),
        ("out_of_coverage", "unsupported", False, 0),
        ("datum", "complete", False, 0),
    ],
)
def test_synthetic_profile_modes_preserve_gaps_boundaries_and_datum(
    client,
    mode,
    expected_state,
    expected_edge,
    expected_gaps,
):
    owner = user_with_role(f"terrain-{mode}", Role.COML)
    _, _, coverage = approved_coverage(owner, mode.upper())
    with override_settings(
        ICT_TERRAIN_PROVIDER=TERRAIN_PROVIDER,
        ICT_TERRAIN_ENGINE=TERRAIN_ENGINE,
        ICT_APPROVED_TERRAIN_CONFIGURATIONS=SYNTHETIC_TERRAIN_APPROVAL,
        ICT_SYNTHETIC_TERRAIN_MODE=mode,
    ):
        queued = post_json(
            client,
            "/api/terrain-analyses/",
            terrain_payload(coverage),
            owner,
        )
        assert queued.status_code == 201, queued.content
        completed = client.post(
            f"/api/terrain-analyses/{queued.json()['id']}/run/",
            **auth_header(owner),
        )
    assert completed.status_code == 200
    body = completed.json()
    assert body["job_state"] == "complete"
    assert body["analysis_state"] == expected_state
    profile = body["result_snapshot"]["profile"]
    assert profile["edge_effect"] is expected_edge
    assert profile["gap_count"] == expected_gaps
    if mode == "ridge":
        assert body["result_snapshot"]["line_of_sight"]["obstruction_count"] > 0
        assert body["result_snapshot"]["comparison"]["materially_different"] is True
    if mode == "out_of_coverage":
        assert body["result_snapshot"]["comparison"]["terrain_continuous_los_distance_m"] is None
        assert body["result_snapshot"]["exclusions"][0]["code"] == "unsupported_condition"
    if mode == "datum":
        source = body["result_snapshot"]["source"]
        assert source["transformation"]["method"] == "constant_offset_fixture"
        sample = profile["samples"][1]
        assert Decimal(sample["terrain_elevation_m"]) - Decimal(
            sample["source_elevation_m"]
        ) == Decimal("10.000")
    if expected_state != "complete":
        assert body["approval_eligible"] is False
        with override_settings(
            ICT_TERRAIN_PROVIDER=TERRAIN_PROVIDER,
            ICT_TERRAIN_ENGINE=TERRAIN_ENGINE,
            ICT_APPROVED_TERRAIN_CONFIGURATIONS=SYNTHETIC_TERRAIN_APPROVAL,
            ICT_SYNTHETIC_TERRAIN_MODE=mode,
        ):
            approval = client.post(
                f"/api/terrain-analyses/{body['id']}/approve/",
                **auth_header(owner),
            )
        assert approval.status_code == 400
        assert "only complete terrain evidence" in str(approval.json()).lower()


@pytest.mark.django_db
@override_settings(
    ICT_TERRAIN_PROVIDER=TERRAIN_PROVIDER,
    ICT_TERRAIN_ENGINE=TERRAIN_ENGINE,
    ICT_APPROVED_TERRAIN_CONFIGURATIONS=SYNTHETIC_TERRAIN_APPROVAL,
    ICT_SYNTHETIC_TERRAIN_MODE="flat",
)
def test_cancel_retry_failure_recovery_and_incident_isolation(client):
    owner = user_with_role("terrain-recovery", Role.COML)
    _, _, coverage = approved_coverage(owner, "RECOVERY")
    queued = post_json(client, "/api/terrain-analyses/", terrain_payload(coverage), owner)

    cancelled = client.post(
        f"/api/terrain-analyses/{queued.json()['id']}/cancel/",
        **auth_header(owner),
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["job_state"] == "cancelled"
    assert cancelled.json()["failure_code"] == "cancelled_by_user"

    retry = client.post(
        f"/api/terrain-analyses/{queued.json()['id']}/retry/",
        **auth_header(owner),
    )
    assert retry.status_code == 201
    assert retry.json()["supersedes"] == queued.json()["id"]

    outsider = user_with_role("terrain-outsider", Role.COML)
    outsider_list = client.get(
        f"/api/terrain-analyses/?incident={coverage.incident_id}",
        **auth_header(outsider),
    )
    assert outsider_list.status_code == 200
    assert outsider_list.json()["count"] == 0
    outsider_detail = client.get(
        f"/api/terrain-analyses/{retry.json()['id']}/",
        **auth_header(outsider),
    )
    assert outsider_detail.status_code == 404

    with override_settings(ICT_SYNTHETIC_TERRAIN_MODE="failure"):
        failed_queue = post_json(
            client,
            "/api/terrain-analyses/",
            terrain_payload(coverage, azimuth_deg="180.000"),
            owner,
        )
        assert failed_queue.status_code == 201
        failed = client.post(
            f"/api/terrain-analyses/{failed_queue.json()['id']}/run/",
            **auth_header(owner),
        )
    assert failed.status_code == 200
    assert failed.json()["job_state"] == "failed"
    assert failed.json()["failure_code"] == "terrain_provider_unavailable"
    assert "fixture" not in failed.json()["failure_message"].lower()

    recovered = client.post(
        f"/api/terrain-analyses/{failed.json()['id']}/retry/",
        **auth_header(owner),
    )
    assert recovered.status_code == 201
    recovered_run = client.post(
        f"/api/terrain-analyses/{recovered.json()['id']}/run/",
        **auth_header(owner),
    )
    assert recovered_run.status_code == 200
    assert recovered_run.json()["job_state"] == "complete"


@pytest.mark.django_db
@override_settings(
    ICT_TERRAIN_PROVIDER=TERRAIN_PROVIDER,
    ICT_TERRAIN_ENGINE=TERRAIN_ENGINE,
    ICT_APPROVED_TERRAIN_CONFIGURATIONS=SYNTHETIC_TERRAIN_APPROVAL,
    ICT_SYNTHETIC_TERRAIN_MODE="flat",
)
def test_provider_cannot_change_requested_path_or_source_evidence(client, monkeypatch):
    owner = user_with_role("terrain-provider-validation", Role.COML)
    _, _, coverage = approved_coverage(owner, "PROVIDER-VALIDATION")
    provider = SyntheticTerrainProfileProvider()
    original_fetch = provider.fetch

    def changed_path(points):
        batch = original_fetch(points)
        batch.samples[1]["latitude"] = "0.000000"
        return batch

    monkeypatch.setattr(provider, "fetch", changed_path)
    monkeypatch.setattr(
        "apps.rf_analysis.terrain.configured_terrain_provider",
        lambda: provider,
    )
    queued = post_json(client, "/api/terrain-analyses/", terrain_payload(coverage), owner)
    assert queued.status_code == 201
    failed = client.post(
        f"/api/terrain-analyses/{queued.json()['id']}/run/",
        **auth_header(owner),
    )
    assert failed.status_code == 200
    assert failed.json()["job_state"] == "failed"
    assert failed.json()["failure_code"] == "terrain_source_invalid"
    assert "0.000000" not in failed.json()["failure_message"]


@pytest.mark.django_db
@override_settings(
    ICT_TERRAIN_PROVIDER=TERRAIN_PROVIDER,
    ICT_TERRAIN_ENGINE=TERRAIN_ENGINE,
    ICT_APPROVED_TERRAIN_CONFIGURATIONS=SYNTHETIC_TERRAIN_APPROVAL,
    ICT_SYNTHETIC_TERRAIN_MODE="flat",
)
def test_completed_evidence_becomes_stale_when_provider_configuration_changes(client):
    owner = user_with_role("terrain-stale-configuration", Role.COML)
    _, _, coverage = approved_coverage(owner, "STALE-CONFIGURATION")
    queued = post_json(client, "/api/terrain-analyses/", terrain_payload(coverage), owner)
    completed = client.post(
        f"/api/terrain-analyses/{queued.json()['id']}/run/",
        **auth_header(owner),
    )
    assert completed.status_code == 200
    assert completed.json()["is_stale"] is False

    with override_settings(ICT_SYNTHETIC_TERRAIN_MODE="ridge"):
        detail = client.get(
            f"/api/terrain-analyses/{queued.json()['id']}/",
            **auth_header(owner),
        )
        approval = client.post(
            f"/api/terrain-analyses/{queued.json()['id']}/approve/",
            **auth_header(owner),
        )
    assert detail.status_code == 200
    assert detail.json()["is_stale"] is True
    assert "terrain_provider_configuration_changed" in detail.json()["stale_reasons"]
    assert approval.status_code == 400
    assert "stale" in str(approval.json()).lower()


@pytest.mark.django_db
def test_terrain_analysis_fails_closed_and_enforces_resource_limits(client):
    owner = user_with_role("terrain-limits", Role.COML)
    _, _, coverage = approved_coverage(owner, "LIMITS")

    status_response = client.get("/api/terrain-analysis-status/", **auth_header(owner))
    assert status_response.status_code == 200
    assert status_response.json()["configured"] is False
    assert status_response.json()["available"] is False
    blocked = post_json(client, "/api/terrain-analyses/", terrain_payload(coverage), owner)
    assert blocked.status_code == 400

    with override_settings(
        ICT_TERRAIN_PROVIDER=TERRAIN_PROVIDER,
        ICT_TERRAIN_ENGINE=TERRAIN_ENGINE,
        ICT_APPROVED_TERRAIN_CONFIGURATIONS=SYNTHETIC_TERRAIN_APPROVAL,
        ICT_SYNTHETIC_TERRAIN_MODE="flat",
        ICT_TERRAIN_MAX_SAMPLES=10,
    ):
        too_many = post_json(
            client,
            "/api/terrain-analyses/",
            terrain_payload(coverage, maximum_distance_m=10_000, sample_interval_m=100),
            owner,
        )
    assert too_many.status_code == 400
    assert "configured limit is 10" in str(too_many.json())


@pytest.mark.django_db
@override_settings(
    ICT_TERRAIN_PROVIDER=TERRAIN_PROVIDER,
    ICT_TERRAIN_ENGINE=TERRAIN_ENGINE,
    ICT_APPROVED_TERRAIN_CONFIGURATIONS=SYNTHETIC_TERRAIN_APPROVAL,
    ICT_SYNTHETIC_TERRAIN_MODE="flat",
)
def test_terrain_history_uses_a_bounded_page_size(client):
    owner = user_with_role("terrain-pagination", Role.COML)
    _, _, coverage = approved_coverage(owner, "PAGINATION")
    for azimuth in range(12):
        queued = post_json(
            client,
            "/api/terrain-analyses/",
            terrain_payload(coverage, azimuth_deg=f"{azimuth}.000"),
            owner,
        )
        assert queued.status_code == 201

    default_page = client.get(
        f"/api/terrain-analyses/?incident={coverage.incident_id}",
        **auth_header(owner),
    )
    maximum_page = client.get(
        f"/api/terrain-analyses/?incident={coverage.incident_id}&page_size=100",
        **auth_header(owner),
    )
    assert default_page.status_code == 200
    assert default_page.json()["count"] == 12
    assert len(default_page.json()["results"]) == 5
    assert maximum_page.status_code == 200
    assert len(maximum_page.json()["results"]) == 10


@pytest.mark.django_db
@override_settings(
    ICT_TERRAIN_PROVIDER=TERRAIN_PROVIDER,
    ICT_TERRAIN_ENGINE=TERRAIN_ENGINE,
    ICT_APPROVED_TERRAIN_CONFIGURATIONS=SYNTHETIC_TERRAIN_APPROVAL,
    ICT_SYNTHETIC_TERRAIN_MODE="flat",
    ICT_TERRAIN_MAX_DISTANCE_M=200_000,
    ICT_TERRAIN_MAX_SAMPLES=1001,
)
def test_maximum_documented_synthetic_profile_is_bounded(client):
    owner = user_with_role("terrain-performance", Role.COML)
    _, _, coverage = approved_coverage(owner, "PERFORMANCE")
    started = time.perf_counter()
    queued = post_json(
        client,
        "/api/terrain-analyses/",
        terrain_payload(
            coverage,
            maximum_distance_m=200_000,
            sample_interval_m=200,
        ),
        owner,
    )
    assert queued.status_code == 201, queued.content
    completed = client.post(
        f"/api/terrain-analyses/{queued.json()['id']}/run/",
        **auth_header(owner),
    )
    elapsed = time.perf_counter() - started
    assert completed.status_code == 200
    assert completed.json()["result_snapshot"]["profile"]["sample_count"] == 1001
    assert elapsed < 5
