import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.authtoken.models import Token

from apps.rf_analysis.elevation import canonical_digest

PROVIDER = "apps.rf_analysis.elevation.SyntheticElevationProvider"


def auth_header(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {"HTTP_AUTHORIZATION": f"Token {token.key}"}


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
        "vertical_crs": "SYNTHETIC:LOCAL",
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


@pytest.mark.django_db
@override_settings(
    ICT_ELEVATION_PROVIDER=PROVIDER,
    ICT_SYNTHETIC_ELEVATION_MODE="flat",
    ICT_APPROVED_ELEVATION_SOURCES=[source_approval("flat")],
)
def test_point_elevation_returns_feet_meters_and_provenance(client):
    user = get_user_model().objects.create_user("elevation-user", password="test-password")
    response = client.get(
        "/api/elevation-point/?latitude=33.06246&longitude=-98.31144",
        **auth_header(user),
    )

    assert response.status_code == 200, response.content
    body = response.json()
    assert body["elevation_m"] == "100.0"
    assert body["elevation_ft"] == "328.1"
    assert body["provider"] == "synthetic-offline"
    assert body["dataset_product"] == "ICT Toolkit deterministic terrain fixture (flat)"
    assert body["vertical_crs"] == "SYNTHETIC:LOCAL"
    assert body["retrieved_at"]
    assert body["warnings"]


@pytest.mark.django_db
def test_point_elevation_validates_coordinates(client):
    user = get_user_model().objects.create_user("elevation-validation", password="test-password")
    headers = auth_header(user)

    missing = client.get("/api/elevation-point/", **headers)
    assert missing.status_code == 400

    latitude = client.get("/api/elevation-point/?latitude=91&longitude=-97", **headers)
    assert latitude.status_code == 400

    longitude = client.get("/api/elevation-point/?latitude=33&longitude=-181", **headers)
    assert longitude.status_code == 400


@pytest.mark.django_db
@override_settings(
    ICT_ELEVATION_PROVIDER=PROVIDER,
    ICT_SYNTHETIC_ELEVATION_MODE="flat",
    ICT_APPROVED_ELEVATION_SOURCES=[],
)
def test_point_elevation_rejects_unapproved_provider(client):
    user = get_user_model().objects.create_user("elevation-unapproved", password="test-password")
    response = client.get(
        "/api/elevation-point/?latitude=33&longitude=-97",
        **auth_header(user),
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "An approved elevation source is not available."


@pytest.mark.django_db
@override_settings(
    ICT_ELEVATION_PROVIDER=PROVIDER,
    ICT_SYNTHETIC_ELEVATION_MODE="failure",
    ICT_APPROVED_ELEVATION_SOURCES=[source_approval("failure")],
)
def test_point_elevation_provider_failure_is_safe_503(client):
    user = get_user_model().objects.create_user("elevation-failure", password="test-password")
    response = client.get(
        "/api/elevation-point/?latitude=33&longitude=-97",
        **auth_header(user),
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "The elevation service is temporarily unavailable."
