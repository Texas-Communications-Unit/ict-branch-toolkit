from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import override_settings
from rest_framework.authtoken.models import Token

from apps.accounts.models import Role, UserRoleAssignment
from apps.audit.models import AuditEvent
from apps.incidents.models import Incident, IncidentMembership
from apps.rf_analysis.elevation import canonical_digest
from apps.rf_analysis.models import (
    ElevationSnapshot,
    HAATCalculation,
    SubscriberProfile,
    SubscriberProfileVersion,
)
from apps.rf_analysis.services import approve_version, create_analysis_snapshot
from apps.sites.models import RadioSite

PROVIDER = "apps.rf_analysis.elevation.SyntheticElevationProvider"


def auth_header(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {"HTTP_AUTHORIZATION": f"Token {token.key}"}


def user_with_role(username, role):
    user = get_user_model().objects.create_user(username, password="safe-test-password")
    UserRoleAssignment.objects.create(user=user, role=role)
    return user


def incident_for(owner, suffix):
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
    return incident


def analysis_inputs(owner, incident, suffix="BASE", antenna_agl_m=Decimal("30.000")):
    site = RadioSite.objects.create(
        incident=incident,
        name=f"Synthetic tower {suffix}",
        latitude=Decimal("31.000000"),
        longitude=Decimal("-97.000000"),
        coordinate_format=RadioSite.CoordinateFormat.DECIMAL,
        created_by=owner,
    )
    profile = SubscriberProfile.objects.create(
        incident=incident,
        name=f"Synthetic fixed station {suffix}",
        profile_type=SubscriberProfile.ProfileType.FIXED,
        description="Synthetic HAAT fixture only",
        created_by=owner,
    )
    version = SubscriberProfileVersion.objects.create(
        profile=profile,
        number=1,
        antenna_center_agl_m=antenna_agl_m,
        input_basis=SubscriberProfileVersion.InputBasis.MODELED_ASSUMPTION,
        notes="Synthetic height assumption",
        created_by=owner,
    )
    version = approve_version(version, owner)
    snapshot = create_analysis_snapshot(
        version,
        label=f"Synthetic approved RF input {suffix}",
        actor=owner,
    )
    return site, version, snapshot


def source_approval(mode):
    descriptor = {
        "provider": "synthetic-offline",
        "dataset_product": f"ICT Toolkit deterministic terrain fixture ({mode})",
        "source_version": "synthetic-terrain-v1",
        "mode": mode,
    }
    return {
        "provider": descriptor["provider"],
        "dataset_product": descriptor["dataset_product"],
        "horizontal_crs": "EPSG:4326",
        "vertical_crs": (
            "SYNTHETIC:LOCAL-OFFSET" if mode == "datum" else "SYNTHETIC:LOCAL"
        ),
        "target_vertical_crs": "SYNTHETIC:LOCAL",
        "resolution_m": "30.000",
        "source_version": descriptor["source_version"],
        "license_terms_url": (
            "https://github.com/Texas-Communications-Unit/ict-branch-toolkit/blob/main/"
            "docs/operations/elevation-and-haat.md#offline-synthetic-fixture"
        ),
        "permitted_use": (
            "Synthetic fixture data only; not terrain, not for operational decision support."
        ),
        "coverage": {"type": "synthetic", "extent": "global"},
        "source_content_sha256": canonical_digest(descriptor),
        "offline": True,
    }


def request_payload(site, rf_input_snapshot, **overrides):
    return {
        "site": str(site.id),
        "rf_input_snapshot": str(rf_input_snapshot.id),
        "radial_count": 8,
        "start_azimuth_deg": "0.000",
        "sampling_interval_m": 1000,
        "inner_distance_m": 3000,
        "outer_distance_m": 16_000,
        "rounding_m": "0.100",
        **overrides,
    }


@pytest.mark.django_db
@override_settings(
    ICT_ELEVATION_PROVIDER=PROVIDER,
    ICT_SYNTHETIC_ELEVATION_MODE="flat",
    ICT_APPROVED_ELEVATION_SOURCES=[source_approval("flat")],
    ICT_ELEVATION_CACHE_TTL_SECONDS=3600,
)
def test_complete_haat_lifecycle_caches_approves_and_retries(client):
    owner = user_with_role("haat-owner", Role.COML)
    incident = incident_for(owner, "LIFECYCLE")
    site, _, rf_snapshot = analysis_inputs(owner, incident)

    provider = client.get("/api/elevation-provider/", **auth_header(owner))
    assert provider.status_code == 200
    assert provider.json()["available"] is True
    assert provider.json()["offline"] is True

    first = client.post(
        "/api/haat-calculations/",
        request_payload(site, rf_snapshot),
        content_type="application/json",
        **auth_header(owner),
    )
    assert first.status_code == 201, first.content
    body = first.json()
    assert body["calculation_state"] == "complete"
    assert body["status"] == "draft"
    assert body["site_elevation_m"] == "100.000"
    assert body["antenna_amsl_m"] == "130.000"
    assert body["average_terrain_m"] == "100.000"
    assert body["haat_m"] == "30.000"
    assert body["sample_count"] == 112
    assert body["excluded_sample_count"] == 0
    assert body["method_version"] == "haat-radial-average-v1-provisional"
    assert body["rf_input_snapshot"] == str(rf_snapshot.id)
    assert body["rf_input_label"] == rf_snapshot.label
    assert body["result_snapshot"]["rf_input_snapshot"] == {
        "id": str(rf_snapshot.id),
        "label": rf_snapshot.label,
        "input_sha256": rf_snapshot.input_sha256,
        "approved_by_id": str(owner.id),
        "approved_at": rf_snapshot.approved_at.isoformat(),
    }
    assert body["algorithm_snapshot"]["azimuths_deg"] == [
        "0.000",
        "45.000",
        "90.000",
        "135.000",
        "180.000",
        "225.000",
        "270.000",
        "315.000",
    ]
    assert body["elevation"]["current_state"] == "complete"
    assert body["elevation"]["sample_sha256"]
    assert "sample_snapshot" not in body["elevation"]
    assert body["result_sha256"]

    elevation_detail = client.get(
        f"/api/elevation-snapshots/{body['elevation_snapshot']}/",
        **auth_header(owner),
    )
    assert elevation_detail.status_code == 200
    assert len(elevation_detail.json()["sample_snapshot"]) == 113
    assert (
        elevation_detail.json()["query_snapshot"]["selected_source"]["provider"]
        == "synthetic-offline"
    )

    second = client.post(
        "/api/haat-calculations/",
        request_payload(site, rf_snapshot),
        content_type="application/json",
        **auth_header(owner),
    )
    assert second.status_code == 201
    assert second.json()["elevation_snapshot"] == body["elevation_snapshot"]
    assert ElevationSnapshot.objects.count() == 1

    approved = client.post(
        f"/api/haat-calculations/{body['id']}/approve/",
        **auth_header(owner),
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["approved_by"] == owner.id

    calculation = HAATCalculation.objects.get(pk=body["id"])
    calculation.haat_m = Decimal("99")
    with pytest.raises(DjangoValidationError, match="immutable"):
        calculation.save()

    retried = client.post(
        f"/api/haat-calculations/{body['id']}/retry/",
        **auth_header(owner),
    )
    assert retried.status_code == 201
    assert retried.json()["supersedes"] == body["id"]
    assert retried.json()["elevation_snapshot"] != body["elevation_snapshot"]
    assert ElevationSnapshot.objects.count() == 2
    assert AuditEvent.objects.filter(action="haat_calculation.created").count() == 2
    assert AuditEvent.objects.filter(action="haat_calculation.approved").count() == 1
    assert AuditEvent.objects.filter(action="haat_calculation.retried").count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("mode", "expected_state", "expected_haat", "expected_source_state"),
    [
        ("flat", "complete", "30.000", "complete"),
        ("slope", "complete", "20.500", "complete"),
        ("rugged", "complete", "27.600", "complete"),
        ("missing", "partial", "30.000", "partial"),
        ("boundary", "partial", "30.000", "partial"),
        ("datum", "complete", "30.000", "complete"),
        ("out_of_coverage", "unavailable", None, "out_of_coverage"),
        ("failure", "unavailable", None, "missing"),
    ],
)
def test_deterministic_terrain_fixtures(
    client,
    settings,
    mode,
    expected_state,
    expected_haat,
    expected_source_state,
):
    settings.ICT_ELEVATION_PROVIDER = PROVIDER
    settings.ICT_SYNTHETIC_ELEVATION_MODE = mode
    settings.ICT_APPROVED_ELEVATION_SOURCES = [source_approval(mode)]
    owner = user_with_role(f"haat-{mode}", Role.COML)
    incident = incident_for(owner, mode.upper())
    site, _, rf_snapshot = analysis_inputs(owner, incident, mode.upper())

    response = client.post(
        "/api/haat-calculations/",
        request_payload(site, rf_snapshot),
        content_type="application/json",
        **auth_header(owner),
    )
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["calculation_state"] == expected_state
    assert body["haat_m"] == expected_haat
    assert body["elevation"]["acquisition_state"] == expected_source_state
    if mode == "datum":
        assert body["elevation"]["vertical_crs"] == "SYNTHETIC:LOCAL-OFFSET"
        assert body["elevation"]["target_vertical_crs"] == "SYNTHETIC:LOCAL"
        assert body["elevation"]["transformation"]["offset_m"] == "10"
    if expected_state != "complete":
        rejected = client.post(
            f"/api/haat-calculations/{body['id']}/approve/",
            **auth_header(owner),
        )
        assert rejected.status_code == 400
    if mode == "failure":
        assert "could not complete retrieval" in body["warnings"][0]


@pytest.mark.django_db
@override_settings(
    ICT_ELEVATION_PROVIDER=PROVIDER,
    ICT_SYNTHETIC_ELEVATION_MODE="flat",
    ICT_APPROVED_ELEVATION_SOURCES=[],
)
def test_unapproved_provider_is_not_called_and_missing_state_is_visible(client):
    owner = user_with_role("haat-unapproved", Role.COML)
    incident = incident_for(owner, "UNAPPROVED")
    site, _, rf_snapshot = analysis_inputs(owner, incident)

    provider = client.get("/api/elevation-provider/", **auth_header(owner))
    assert provider.status_code == 200
    assert provider.json()["configured"] is True
    assert provider.json()["approved"] is False
    assert provider.json()["available"] is False

    response = client.post(
        "/api/haat-calculations/",
        request_payload(site, rf_snapshot),
        content_type="application/json",
        **auth_header(owner),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["calculation_state"] == "unavailable"
    assert body["elevation"]["acquisition_state"] == "missing"
    assert "not approved" in body["warnings"][0]


@pytest.mark.django_db
@override_settings(
    ICT_ELEVATION_PROVIDER=PROVIDER,
    ICT_SYNTHETIC_ELEVATION_MODE="flat",
    ICT_APPROVED_ELEVATION_SOURCES=[source_approval("flat")],
)
def test_incident_scope_permissions_and_input_validation(client):
    owner = user_with_role("haat-scope-owner", Role.COML)
    outsider = user_with_role("haat-scope-outsider", Role.COMT)
    read_only = user_with_role("haat-scope-reader", Role.READ_ONLY)
    incident = incident_for(owner, "SCOPE")
    site, _, rf_snapshot = analysis_inputs(owner, incident)
    IncidentMembership.objects.create(
        incident=incident,
        user=read_only,
        role=Role.READ_ONLY,
        assigned_by=owner,
    )

    denied = client.post(
        "/api/haat-calculations/",
        request_payload(site, rf_snapshot),
        content_type="application/json",
        **auth_header(read_only),
    )
    assert denied.status_code == 403
    hidden = client.get(
        f"/api/haat-calculations/?incident={incident.id}",
        **auth_header(outsider),
    )
    assert hidden.status_code == 200
    assert hidden.json()["results"] == []

    other_incident = incident_for(owner, "OTHER-SCOPE")
    _, _, other_snapshot = analysis_inputs(owner, other_incident, "OTHER-SCOPE")
    cross_incident = client.post(
        "/api/haat-calculations/",
        request_payload(site, other_snapshot),
        content_type="application/json",
        **auth_header(owner),
    )
    assert cross_incident.status_code == 400

    _, _, missing_height_snapshot = analysis_inputs(
        owner,
        incident,
        "MISSING-HEIGHT",
        antenna_agl_m=None,
    )
    missing_height = client.post(
        "/api/haat-calculations/",
        request_payload(site, missing_height_snapshot),
        content_type="application/json",
        **auth_header(owner),
    )
    assert missing_height.status_code == 400

    invalid_grid = client.post(
        "/api/haat-calculations/",
        request_payload(site, rf_snapshot, outer_distance_m=3000),
        content_type="application/json",
        **auth_header(owner),
    )
    assert invalid_grid.status_code == 400

    oversized_grid = client.post(
        "/api/haat-calculations/",
        request_payload(
            site,
            rf_snapshot,
            radial_count=360,
            sampling_interval_m=10,
            inner_distance_m=1,
            outer_distance_m=100_000,
        ),
        content_type="application/json",
        **auth_header(owner),
    )
    assert oversized_grid.status_code == 400
    assert "10000-sample safety limit" in str(oversized_grid.json())


@pytest.mark.django_db
@override_settings(
    ICT_ELEVATION_PROVIDER=PROVIDER,
    ICT_SYNTHETIC_ELEVATION_MODE="flat",
    ICT_APPROVED_ELEVATION_SOURCES=[source_approval("flat")],
    ICT_ELEVATION_CACHE_TTL_SECONDS=0,
)
def test_expired_snapshot_reports_stale_and_is_not_reused(client):
    owner = user_with_role("haat-stale", Role.COML)
    incident = incident_for(owner, "STALE")
    site, _, rf_snapshot = analysis_inputs(owner, incident)

    first = client.post(
        "/api/haat-calculations/",
        request_payload(site, rf_snapshot),
        content_type="application/json",
        **auth_header(owner),
    )
    assert first.status_code == 201
    assert first.json()["elevation"]["current_state"] == "stale"
    second = client.post(
        "/api/haat-calculations/",
        request_payload(site, rf_snapshot),
        content_type="application/json",
        **auth_header(owner),
    )
    assert second.status_code == 201
    assert second.json()["elevation_snapshot"] != first.json()["elevation_snapshot"]
    snapshot = ElevationSnapshot.objects.get(pk=first.json()["elevation_snapshot"])
    with pytest.raises(DjangoValidationError, match="retained"):
        snapshot.delete()


@pytest.mark.django_db
def test_cache_identity_includes_selected_source_descriptor(client, settings):
    settings.ICT_ELEVATION_PROVIDER = PROVIDER
    settings.ICT_SYNTHETIC_ELEVATION_MODE = "flat"
    settings.ICT_APPROVED_ELEVATION_SOURCES = [source_approval("flat")]
    settings.ICT_ELEVATION_CACHE_TTL_SECONDS = 3600
    owner = user_with_role("haat-source-change", Role.COML)
    incident = incident_for(owner, "SOURCE-CHANGE")
    site, _, rf_snapshot = analysis_inputs(owner, incident)

    first = client.post(
        "/api/haat-calculations/",
        request_payload(site, rf_snapshot),
        content_type="application/json",
        **auth_header(owner),
    )
    assert first.status_code == 201
    assert first.json()["haat_m"] == "30.000"

    settings.ICT_SYNTHETIC_ELEVATION_MODE = "slope"
    settings.ICT_APPROVED_ELEVATION_SOURCES = [source_approval("slope")]
    second = client.post(
        "/api/haat-calculations/",
        request_payload(site, rf_snapshot),
        content_type="application/json",
        **auth_header(owner),
    )
    assert second.status_code == 201
    assert second.json()["haat_m"] == "20.500"
    assert second.json()["elevation_snapshot"] != first.json()["elevation_snapshot"]
    assert ElevationSnapshot.objects.count() == 2
