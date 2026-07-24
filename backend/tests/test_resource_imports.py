import json
from copy import deepcopy
from io import StringIO
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import override_settings
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

NIFOG_APPROVAL = {
    "source_type": "cisa_nifog",
    "version": "2.02",
    "authoritative_url": (
        "https://www.cisa.gov/sites/default/files/2024-12/"
        "NIFOG%202.02_508%20FINAL%20VERSION%2012%2003%202024.pdf"
    ),
    "content_sha256": "45c2f5d94861b3ed1b80f7ce5962a160fdd56092211586bdee711b68ca3d3142",
}


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


def bundled_nifog_payload():
    path = Path(settings.BASE_DIR) / "data" / "reference" / "nifog-2.02.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_bundled_nifog_release_has_reviewed_counts_and_representative_records():
    payload = bundled_nifog_payload()
    serializer = ChannelImportSerializer(data=payload)
    assert serializer.is_valid(), serializer.errors
    assert payload["source"]["authoritative_url"] == NIFOG_APPROVAL["authoritative_url"]
    assert payload["release"]["content_sha256"] == NIFOG_APPROVAL["content_sha256"]
    assert len(payload["conventional_channels"]) == 230
    assert len(payload["trunked_talkgroups"]) == 32

    conventional = {record["identifier"]: record for record in payload["conventional_channels"]}
    assert conventional["LLAW1"]["rx_frequency_hz"] == 39_460_000
    assert conventional["LLAW1"]["tx_frequency_hz"] == 45_860_000
    assert conventional["LLAW1"]["source_pages"] == "28"
    assert conventional["LLAW1"]["bandwidth_hz"] == 16_000
    assert conventional["VTAC17"]["emission_designator"] == "11K0F3E"
    assert conventional["VTAC17"]["bandwidth_hz"] == 11_000
    assert conventional["IR 1"]["tx_squelch"] == "167.9"
    assert conventional["LE 2"]["mode"] == "p25"
    assert conventional["MED-9"]["source_pages"] == "41"
    assert conventional["7CALL50"]["rx_squelch"] == "$F7E"
    assert conventional["7-US-01"]["mode"] == "other"
    assert conventional["DEPLOY-A"]["source_pages"] == "54"
    assert conventional["8CALL90"]["rx_frequency_hz"] == 851_012_500
    assert conventional["VHF Marine Ch. 17"]["source_pages"] == "63"
    assert conventional["VHF Marine Ch. 17"]["band"] == "VHF"

    talkgroups = {record["identifier"]: record for record in payload["trunked_talkgroups"]}
    assert talkgroups["YY-CALL-YY"]["talkgroup_id"] == 201
    assert talkgroups["ZZ-TAC-ZZ9"]["talkgroup_id"] == 109
    assert all(record["source_pages"] for record in payload["trunked_talkgroups"])


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


@pytest.mark.django_db
@override_settings(ICT_APPROVED_REFERENCE_IMPORTS=[NIFOG_APPROVAL])
def test_approved_bundled_nifog_import_is_searchable_and_preserves_provenance(client):
    admin = get_user_model().objects.create_superuser("nifog-admin", password="safe-test-password")
    payload = bundled_nifog_payload()
    payload["dry_run"] = False
    serializer = ChannelImportSerializer(data=payload)
    assert serializer.is_valid(), serializer.errors

    record = apply_import(
        validated_data=serializer.validated_data,
        raw_payload=payload,
        actor=admin,
    )
    assert record.conventional_count == 230
    assert record.talkgroup_count == 32
    release = ResourceRelease.objects.get()
    assert release.document_title == "National Interoperability Field Operations Guide Version 2.02"
    assert release.publisher == "Cybersecurity and Infrastructure Security Agency"
    assert release.retrieved_on.isoformat() == "2026-07-23"

    channel = ConventionalChannel.objects.get(identifier="VTAC17")
    assert channel.channel_use == "Tactical"
    assert channel.source_pages == "31"
    assert "does not itself authorize operation" in channel.authorization

    response = client.get(
        "/api/conventional-channels/?search=VTAC17",
        **auth_header(admin),
    )
    assert response.status_code == 200
    identifiers = {item["identifier"] for item in response.json()["results"]}
    assert identifiers == {"VTAC17", "VTAC17D"}


@pytest.mark.django_db
@override_settings(ICT_APPROVED_REFERENCE_IMPORTS=[NIFOG_APPROVAL])
def test_bundled_nifog_command_is_idempotent():
    get_user_model().objects.create_superuser("command-admin", password="safe-test-password")
    output = StringIO()
    command = [
        "import_bundled_nifog",
        "--apply",
        "--if-approved",
        "--username",
        "command-admin",
    ]
    call_command(*command, stdout=output)
    call_command(*command, stdout=output)

    assert ResourceRelease.objects.count() == 1
    assert ResourceImport.objects.count() == 1
    assert ConventionalChannel.objects.count() == 230
    assert TrunkedTalkgroup.objects.count() == 32
    assert "already imported" in output.getvalue()


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
