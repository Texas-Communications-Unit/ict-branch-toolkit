import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.fcc_data.models import FccImportBatch
from apps.incidents.models import Incident, OperationalPeriod
from apps.resources.models import ResourceRelease, ResourceSource


@pytest.mark.django_db
def test_purge_incident_data_requires_backup_and_preserves_fcc():
    user = get_user_model().objects.create_superuser(
        "reset-admin", "reset-admin@example.invalid", "safe-test-password"
    )
    incident = Incident.objects.create(name="Old evaluation", created_by=user)
    OperationalPeriod.objects.create(
        incident=incident,
        name="Old period",
        starts_at="2026-01-01T00:00:00Z",
        ends_at="2026-01-01T12:00:00Z",
        created_by=user,
    )
    batch = FccImportBatch.objects.create(
        dataset=FccImportBatch.Dataset.ASR,
        archive_name="public-fcc.zip",
        source_url="https://data.fcc.gov/public-fcc.zip",
        content_sha256="1" * 64,
        parser_version="test-v1",
        retrieved_at="2026-01-01T00:00:00Z",
        imported_by=user,
    )
    synthetic_source = ResourceSource.objects.create(
        slug="old-fixture", name="Old fixture", source_type=ResourceSource.Type.SYNTHETIC
    )
    ResourceRelease.objects.create(
        source=synthetic_source,
        version="SYN-1",
        effective_status=ResourceRelease.Status.EFFECTIVE,
        content_sha256="2" * 64,
        imported_by=user,
    )
    call_command(
        "purge_incident_data",
        confirm="DELETE-ALL-INCIDENT-DATA",
        verified_backup_sha256="a" * 64,
    )

    assert not Incident.objects.exists()
    assert not OperationalPeriod.objects.exists()
    assert FccImportBatch.objects.filter(pk=batch.pk).exists()
    assert not ResourceSource.objects.filter(pk=synthetic_source.pk).exists()
