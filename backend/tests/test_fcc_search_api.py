from datetime import UTC, datetime

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.accounts.models import Role, UserRoleAssignment
from apps.fcc_data.models import AntennaStructure, FccImportBatch, UlsFrequency, UlsLicense


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
    AntennaStructure.objects.create(
        batch=batch,
        registration_number="1234567",
        owner_name="Synthetic County",
        latitude="33.2000000",
        longitude="-97.1000000",
    )

    client = APIClient()
    client.force_authenticate(user)
    licenses = client.get("/api/fcc-licenses/?search=WQTEST1&state=TX")
    structures = client.get("/api/fcc-antenna-structures/?search=1234567")

    assert licenses.status_code == 200
    assert licenses.data["count"] == 1
    assert licenses.data["results"][0]["frequencies_hz"] == [155_000_000]
    assert licenses.data["results"][0]["batch"]["content_sha256"] == "a" * 64
    assert structures.status_code == 200
    assert structures.data["count"] == 1


@pytest.mark.django_db
def test_fcc_search_requires_authentication(client):
    assert client.get("/api/fcc-licenses/?search=test").status_code in {401, 403}
