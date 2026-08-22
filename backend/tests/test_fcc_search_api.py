from datetime import UTC, datetime

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.accounts.models import Role, UserRoleAssignment
from apps.fcc_data.models import (
    AntennaStructure,
    FccImportBatch,
    UlsEmission,
    UlsFrequency,
    UlsLicense,
    UlsLocation,
)


@pytest.mark.django_db
def test_authenticated_library_user_searches_current_fcc_records():
    user = get_user_model().objects.create_user(username="fcc-reader", password="test-only")
    UserRoleAssignment.objects.create(user=user, role=Role.READ_ONLY)
    batch = FccImportBatch.objects.create(
        dataset=FccImportBatch.Dataset.ULS_PRIVATE,
        archive_name="l_LMpriv.zip",
        source_url="https://data.fcc.gov/download/pub/uls/complete/l_LMpriv.zip",
        content_sha256="a" * 64,
        parser_version="test",
        retrieved_at=datetime(2026, 8, 20, tzinfo=UTC),
        imported_by=user,
    )
    license_record = UlsLicense.objects.create(
        batch=batch,
        unique_system_identifier="100",
        call_sign="WQTEST1",
        license_status="A",
        radio_service_code="PW",
        selection_rule="government",
        licensee_name="Synthetic County",
        city="Denton",
        state="TX",
    )
    UlsFrequency.objects.create(
        license=license_record,
        location_number=1,
        antenna_number=1,
        frequency_hz=155_000_000,
    )
    UlsLocation.objects.create(
        license=license_record,
        location_number=1,
        city="Denton",
        state="TX",
        asr_registration_number="1234567",
        latitude="33.2000000",
        longitude="-97.1000000",
    )
    UlsEmission.objects.create(
        license=license_record,
        location_number=1,
        antenna_number=1,
        frequency_hz=155_000_000,
        emission_designator="11K2F3E",
    )
    AntennaStructure.objects.create(
        batch=batch,
        registration_number="1234567",
        unique_system_identifier="200",
        owner_name="Synthetic County",
        latitude="33.2000000",
        longitude="-97.1000000",
    )

    client = APIClient()
    client.force_authenticate(user)
    licenses = client.get("/api/fcc-licenses/?search=WQTEST1&state=TX")
    structures = client.get("/api/fcc-antenna-structures/?search=1234567")
    map_structures = client.get("/api/fcc-antenna-structures/?west=-98&south=33&east=-97&north=34")

    assert licenses.status_code == 200
    assert licenses.data["count"] == 1
    assert licenses.data["results"][0]["frequencies_hz"] == [155_000_000]
    assert licenses.data["results"][0]["batch"]["content_sha256"] == "a" * 64
    assert structures.status_code == 200
    assert structures.data["count"] == 1
    assert "regKey=200" in structures.data["results"][0]["fcc_record_url"]
    assert map_structures.status_code == 200
    assert map_structures.data["count"] == 1

    details = client.get(
        f"/api/fcc-antenna-structures/{structures.data['results'][0]['id']}/tower-details/"
    )
    assert details.status_code == 200
    assert details.data["license_count"] == 1
    assert details.data["licenses"][0]["call_sign"] == "WQTEST1"
    assert "licKey=100" in details.data["licenses"][0]["fcc_record_url"]
    location = details.data["licenses"][0]["tower_locations"][0]
    assert location["frequencies"][0]["frequency_hz"] == 155_000_000
    assert location["emissions"][0]["emission_designator"] == "11K2F3E"
    assert "does not authorize" in details.data["disclaimer"]


@pytest.mark.django_db
def test_fcc_map_features_cluster_filter_and_expand(client):
    user = get_user_model().objects.create_user(username="fcc-map-reader")
    UserRoleAssignment.objects.create(user=user, role=Role.READ_ONLY)
    batch = FccImportBatch.objects.create(
        dataset=FccImportBatch.Dataset.ASR,
        archive_name="r_tower.zip",
        source_url="https://data.fcc.gov/download/pub/uls/complete/r_tower.zip",
        content_sha256="b" * 64,
        parser_version="test",
        retrieved_at=datetime(2026, 8, 22, tzinfo=UTC),
        imported_by=user,
    )
    AntennaStructure.objects.create(
        batch=batch,
        registration_number="2000001",
        unique_system_identifier="301",
        owner_name="Synthetic County Alpha",
        status_code="C",
        structure_type="GTOWER",
        latitude="33.2000000",
        longitude="-97.1000000",
    )
    AntennaStructure.objects.create(
        batch=batch,
        registration_number="2000002",
        unique_system_identifier="302",
        owner_name="Synthetic County Bravo",
        status_code="C",
        structure_type="GTOWER",
        latitude="33.2001000",
        longitude="-97.1001000",
    )
    client = APIClient()
    client.force_authenticate(user)
    bounds = "west=-98&south=33&east=-97&north=34"

    clustered = client.get(f"/api/fcc-antenna-structures/map-features/?{bounds}&zoom=7")
    expanded = client.get(f"/api/fcc-antenna-structures/map-features/?{bounds}&zoom=16")
    filtered = client.get(f"/api/fcc-antenna-structures/map-features/?{bounds}&zoom=7&search=Alpha")

    assert clustered.status_code == 200
    assert clustered.data["count"] == 2
    assert clustered.data["feature_count"] == 1
    assert clustered.data["results"][0]["kind"] == "cluster"
    assert clustered.data["results"][0]["count"] == 2
    assert expanded.status_code == 200
    assert expanded.data["feature_count"] == 2
    assert {item["kind"] for item in expanded.data["results"]} == {"tower"}
    assert filtered.status_code == 200
    assert filtered.data["count"] == 1
    assert filtered.data["results"][0]["tower"]["registration_number"] == "2000001"


@pytest.mark.django_db
def test_fcc_map_bounds_are_complete_and_valid(client):
    user = get_user_model().objects.create_user(username="fcc-bounds-reader")
    UserRoleAssignment.objects.create(user=user, role=Role.READ_ONLY)
    client = APIClient()
    client.force_authenticate(user)

    incomplete = client.get("/api/fcc-antenna-structures/?west=-98")
    reversed_bounds = client.get("/api/fcc-antenna-structures/?west=-97&south=33&east=-98&north=34")

    assert incomplete.status_code == 400
    assert reversed_bounds.status_code == 400


@pytest.mark.django_db
def test_fcc_search_requires_authentication(client):
    assert client.get("/api/fcc-licenses/?search=test").status_code in {401, 403}
