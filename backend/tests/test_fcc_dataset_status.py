from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from drf_spectacular.generators import SchemaGenerator
from rest_framework.test import APIClient

from apps.accounts.models import Role, UserRoleAssignment
from apps.fcc_data.models import FccImportBatch
from apps.fcc_data.status import dataset_status

NOW = datetime(2026, 11, 4, 12, tzinfo=UTC)


@pytest.fixture
def reader(db):
    user = get_user_model().objects.create_user(username="synthetic-fcc-reader")
    UserRoleAssignment.objects.create(user=user, role=Role.READ_ONLY)
    return user


def batch(reader, **changes):
    return FccImportBatch.objects.create(
        **(
            {
                "dataset": "asr",
                "archive_name": "r_tower.zip",
                "source_url": "https://data.fcc.gov/download/pub/uls/complete/r_tower.zip",
                "content_sha256": "a" * 64,
                "parser_version": "synthetic-v1",
                "retrieved_at": NOW - timedelta(days=8),
                "record_counts": {"antenna_structures": 21},
                "imported_by": reader,
            }
            | changes
        )
    )


def status():
    with patch("apps.fcc_data.status.timezone.now", return_value=NOW):
        return dataset_status()


def test_all_three_missing_datasets_use_three_metadata_queries(reader, django_assert_num_queries):
    with django_assert_num_queries(3):
        result = status()
    assert [row["dataset"] for row in result["datasets"]] == [
        "asr",
        "uls_private",
        "uls_commercial",
    ]
    assert all(row["status"] == "not_imported" for row in result["datasets"])
    assert all(row["retrieved_at"] is None for row in result["datasets"])


def test_only_current_metadata_is_used_and_age_does_not_claim_latest_source_check(reader):
    current = batch(reader)
    batch(
        reader, is_current=False, content_sha256="b" * 64, record_counts={"antenna_structures": 999}
    )
    FccImportBatch.objects.filter(pk=current.pk).update(imported_at=NOW - timedelta(days=7))
    row = status()["datasets"][0]
    assert row["status"] == "available"
    assert row["retrieved_age_days"] == 8
    assert row["record_counts"] == {"antenna_structures": 21}
    assert row["last_checked_at"] is None
    assert row["timestamp_warning"] is False


def test_conflicting_current_imports_do_not_silently_select_one(reader):
    batch(reader)
    batch(reader, content_sha256="b" * 64)
    row = status()["datasets"][0]
    assert row["status"] == "ambiguous"
    assert row["content_sha256"] is None
    assert row["record_counts"] == {"antenna_structures": None}


@pytest.mark.parametrize("field", ["retrieved_at", "imported_at"])
def test_future_timestamps_are_explicit_not_negative_freshness(reader, field):
    current = batch(reader)
    FccImportBatch.objects.filter(pk=current.pk).update(**{field: NOW + timedelta(days=1)})
    row = status()["datasets"][0]
    assert row["timestamp_warning"] is True
    assert row["retrieved_age_days"] is None


@pytest.mark.parametrize("invalid", [-1, True, "10", 2**53, {"private": "hidden"}])
def test_counts_are_allowlisted_safe_nonnegative_integer_metadata(reader, invalid):
    batch(reader, record_counts={"antenna_structures": invalid, "operator_secret": "hidden"})
    assert status()["datasets"][0]["record_counts"] == {"antenna_structures": None}


def test_untrusted_provenance_and_operator_details_are_not_exposed(reader):
    batch(reader, source_url="https://example.invalid/private", archive_name="/private/file.zip")
    row = status()["datasets"][0]
    assert row["source_url"] is None
    assert row["archive_name"] is None
    assert "imported_by" not in row


def test_api_requires_existing_library_policy_and_is_read_only(reader, settings):
    client = APIClient()
    assert client.get("/api/fcc-dataset-status/").status_code in (401, 403)
    outsider = get_user_model().objects.create_user(username="synthetic-no-role")
    client.force_authenticate(outsider)
    settings.ICT_ROLE_POLICY_OVERRIDES = {Role.READ_ONLY: []}
    assert client.get("/api/fcc-dataset-status/").status_code == 403
    settings.ICT_ROLE_POLICY_OVERRIDES = {}
    client.force_authenticate(reader)
    result = client.get("/api/fcc-dataset-status/")
    assert result.status_code == 200
    assert len(result.data["datasets"]) == 3
    assert client.post("/api/fcc-dataset-status/", {}).status_code == 405
    assert FccImportBatch.objects.count() == 0


def test_schema_matches_the_object_envelope_instead_of_an_inferred_list(reader):
    schema = SchemaGenerator().get_schema(request=None, public=True)
    response = schema["paths"]["/api/fcc-dataset-status/"]["get"]["responses"]["200"]
    assert response["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/FccDatasetStatusResponse"
    }
