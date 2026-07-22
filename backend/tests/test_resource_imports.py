from copy import deepcopy

import pytest
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token

from apps.audit.models import AuditEvent
from apps.resources.models import (
    ConventionalChannel,
    ResourceImport,
    ResourceRelease,
    ResourceSource,
    TrunkedTalkgroup,
)
from apps.resources.serializers import ChannelImportSerializer
from apps.resources.services import apply_import


def auth_header(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {"HTTP_AUTHORIZATION": f"Token {token.key}"}


@pytest.fixture
def synthetic_payload():
    return {
        "dry_run": True,
        "source": {
            "slug": "synthetic-p1-1",
            "name": "Synthetic P1.1 Fixture",
            "source_type": "synthetic",
            "authoritative_url": "https://example.invalid/synthetic-p1-1",
        },
        "release": {
            "version": "SYN-1",
            "released_on": "2026-07-22",
            "effective_status": "effective",
            "content_sha256": "0" * 64,
        },
        "conventional_channels": [
            {
                "identifier": "SYN-VHF-1",
                "name": "Synthetic VHF Calling",
                "band": "VHF",
                "rx_frequency_hz": 155000000,
                "tx_frequency_hz": 155000000,
                "bandwidth_hz": 12500,
                "mode": "analog_fm",
                "rx_squelch": "CSQ",
                "tx_squelch": "CSQ",
                "restrictions": "Synthetic exercise use only",
                "notes": "Not an assigned or authorized frequency",
                "is_active": True,
            }
        ],
        "trunked_talkgroups": [
            {
                "identifier": "SYN-TG-1",
                "name": "Synthetic Operations",
                "system_name": "Synthetic Regional System",
                "talkgroup_id": 65001,
                "mode": "P25 Phase 2",
                "restrictions": "Synthetic exercise use only",
                "notes": "Not a real talkgroup",
                "is_active": True,
            }
        ],
    }


@pytest.fixture
def admin_user():
    return get_user_model().objects.create_superuser(
        "rollback-admin", password="safe-test-password"
    )


@pytest.mark.django_db
def test_admin_dry_run_has_no_side_effects(client, synthetic_payload):
    admin = get_user_model().objects.create_superuser("admin", password="safe-test-password")
    response = client.post(
        "/api/channel-imports/",
        synthetic_payload,
        content_type="application/json",
        **auth_header(admin),
    )
    assert response.status_code == 200
    assert response.json()["valid"] is True
    assert response.json()["would_create"]["conventional_channels"] == 1
    assert ResourceSource.objects.count() == 0
    assert ResourceRelease.objects.count() == 0


@pytest.mark.django_db
def test_only_administrator_can_import(client, synthetic_payload):
    reader = get_user_model().objects.create_user("reader", password="safe-test-password")
    response = client.post(
        "/api/channel-imports/",
        synthetic_payload,
        content_type="application/json",
        **auth_header(reader),
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_apply_import_preserves_distinct_resource_types_and_provenance(client, synthetic_payload):
    admin = get_user_model().objects.create_superuser("admin", password="safe-test-password")
    payload = deepcopy(synthetic_payload)
    payload["dry_run"] = False
    response = client.post(
        "/api/channel-imports/",
        payload,
        content_type="application/json",
        **auth_header(admin),
    )
    assert response.status_code == 201
    assert ResourceRelease.objects.get().version == "SYN-1"
    assert ConventionalChannel.objects.get().rx_frequency_hz == 155000000
    assert TrunkedTalkgroup.objects.get().talkgroup_id == 65001
    assert ResourceImport.objects.get().conventional_count == 1
    assert AuditEvent.objects.filter(action="resource_release.imported").exists()

    payload["dry_run"] = True
    duplicate = client.post(
        "/api/channel-imports/",
        payload,
        content_type="application/json",
        **auth_header(admin),
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["valid"] is False


@pytest.mark.django_db
def test_unapproved_cisa_release_can_be_previewed_but_not_applied(client, synthetic_payload):
    admin = get_user_model().objects.create_superuser("admin", password="safe-test-password")
    payload = deepcopy(synthetic_payload)
    payload["source"].update(
        {
            "slug": "cisa-nifog",
            "name": "National Interoperability Field Operations Guide",
            "source_type": "cisa_nifog",
            "authoritative_url": "https://www.cisa.gov/example.pdf",
        }
    )
    payload["release"]["version"] = "2.02"
    preview = client.post(
        "/api/channel-imports/",
        payload,
        content_type="application/json",
        **auth_header(admin),
    )
    assert preview.status_code == 200
    assert preview.json()["approval_required"] is True

    payload["dry_run"] = False
    applied = client.post(
        "/api/channel-imports/",
        payload,
        content_type="application/json",
        **auth_header(admin),
    )
    assert applied.status_code == 403
    assert ResourceRelease.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_import_transaction_rolls_back_on_persistence_failure(
    admin_user, synthetic_payload, monkeypatch
):
    serializer = ChannelImportSerializer(data={**synthetic_payload, "dry_run": False})
    assert serializer.is_valid(), serializer.errors

    def fail_bulk_create(*args, **kwargs):
        raise RuntimeError("synthetic persistence failure")

    monkeypatch.setattr(ConventionalChannel.objects, "bulk_create", fail_bulk_create)
    with pytest.raises(RuntimeError, match="synthetic persistence failure"):
        apply_import(
            validated_data=serializer.validated_data,
            raw_payload=synthetic_payload,
            actor=admin_user,
        )
    assert ResourceSource.objects.count() == 0
    assert ResourceRelease.objects.count() == 0
