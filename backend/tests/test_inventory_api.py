import base64
from datetime import UTC, datetime

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.models import Role, UserRoleAssignment
from apps.audit.models import AuditEvent
from apps.incidents.models import Incident, IncidentMembership
from apps.inventory.models import (
    Asset,
    AssetCheckout,
    ChargingRecord,
    MaintenanceRecord,
    ProgrammingRecord,
)

TEST_KEY = base64.urlsafe_b64encode(b"0" * 32).decode("ascii")


def _user(username, role):
    user = get_user_model().objects.create_user(username=username, password="unused")
    UserRoleAssignment.objects.create(user=user, role=role, assigned_by=user)
    return user


def _incident(owner, member=None):
    incident = Incident.objects.create(name="Synthetic Exercise", created_by=owner)
    IncidentMembership.objects.create(
        incident=incident,
        user=owner,
        role=Role.COML,
        assigned_by=owner,
    )
    if member:
        IncidentMembership.objects.create(
            incident=incident,
            user=member,
            role=Role.READ_ONLY,
            assigned_by=owner,
        )
    return incident


@pytest.mark.django_db
@override_settings(ICT_INVENTORY_ENCRYPTION_KEY=TEST_KEY)
def test_incident_members_can_view_driver_license_and_normal_return_deletes_it():
    manager = _user("inventory-manager", Role.COML)
    reader = _user("incident-reader", Role.READ_ONLY)
    incident = _incident(manager, reader)
    asset = Asset.objects.create(
        asset_id="RADIO-12000",
        category=Asset.Category.RADIO,
        manufacturer="Synthetic",
        model="Portable",
        serial_number="TEST-SERIAL-1",
        created_by=manager,
    )
    client = APIClient()
    client.force_authenticate(manager)

    created = client.post(
        "/api/inventory-checkouts/",
        {
            "incident": str(incident.id),
            "assets": [str(asset.id)],
            "assigned_name": "Test Assignee",
            "assigned_organization": "Synthetic County",
            "driver_license_jurisdiction": "TX",
            "driver_license_number": "12345678",
        },
        format="json",
    )

    assert created.status_code == 201
    checkout = AssetCheckout.objects.get()
    assert checkout.driver_license_ciphertext != "12345678"
    assert checkout.driver_license_last_four == "5678"
    client.force_authenticate(reader)
    listing = client.get(f"/api/inventory-checkouts/?incident={incident.id}")
    assert listing.status_code == 200
    assert listing.json()["results"][0]["driver_license_number"] == "12345678"
    assert AuditEvent.objects.filter(action="inventory.driver_license_records_viewed").exists()

    client.force_authenticate(manager)
    returned = client.post(
        f"/api/inventory-checkouts/{checkout.id}/return/",
        {"condition": "normal", "hold_reason": ""},
        format="json",
    )
    assert returned.status_code == 200
    checkout.refresh_from_db()
    asset.refresh_from_db()
    assert checkout.driver_license_ciphertext == ""
    assert checkout.driver_license_last_four == ""
    assert asset.status == Asset.Status.IN_SERVICE
    assert returned.json()["driver_license_number"] is None


@pytest.mark.django_db
@override_settings(ICT_INVENTORY_ENCRYPTION_KEY=TEST_KEY)
def test_damaged_radio_retains_license_under_accountability_hold():
    manager = _user("damage-manager", Role.COML)
    incident = _incident(manager)
    asset = Asset.objects.create(
        asset_id="RADIO-DAMAGED",
        category=Asset.Category.RADIO,
        created_by=manager,
    )
    client = APIClient()
    client.force_authenticate(manager)
    created = client.post(
        "/api/inventory-checkouts/",
        {
            "incident": str(incident.id),
            "assets": [str(asset.id)],
            "assigned_name": "Damage Test",
            "assigned_organization": "Synthetic Agency",
            "driver_license_jurisdiction": "OK",
            "driver_license_number": "A123456789",
        },
        format="json",
    )
    checkout_id = created.json()[0]["id"]

    returned = client.post(
        f"/api/inventory-checkouts/{checkout_id}/return/",
        {"condition": "damaged", "hold_reason": "Cracked display; report TEST-1."},
        format="json",
    )

    assert returned.status_code == 200
    checkout = AssetCheckout.objects.get(pk=checkout_id)
    checkout.asset.refresh_from_db()
    assert checkout.state == AssetCheckout.State.HOLD
    assert checkout.driver_license_ciphertext
    assert returned.json()["driver_license_number"] == "A123456789"
    assert checkout.asset.status == Asset.Status.MAINTENANCE

    resolved = client.post(
        f"/api/inventory-checkouts/{checkout_id}/resolve-hold/",
        {
            "asset_status": "maintenance",
            "resolution_note": "Synthetic incident report closed.",
        },
        format="json",
    )
    assert resolved.status_code == 200
    checkout.refresh_from_db()
    assert checkout.state == AssetCheckout.State.RETURNED
    assert checkout.driver_license_ciphertext == ""
    assert checkout.driver_license_last_four == ""
    assert checkout.hold_resolved_by == manager
    assert checkout.hold_resolved_at is not None
    assert resolved.json()["driver_license_number"] is None
    assert AuditEvent.objects.filter(
        action="inventory.accountability_hold_resolved_license_deleted"
    ).exists()


@pytest.mark.django_db
@override_settings(ICT_INVENTORY_ENCRYPTION_KEY=TEST_KEY)
def test_user_outside_incident_cannot_view_checkout_or_license():
    manager = _user("scope-manager", Role.COML)
    outsider = _user("scope-outsider", Role.READ_ONLY)
    incident = _incident(manager)
    asset = Asset.objects.create(
        asset_id="RADIO-SCOPED",
        category=Asset.Category.RADIO,
        created_by=manager,
    )
    client = APIClient()
    client.force_authenticate(manager)
    created = client.post(
        "/api/inventory-checkouts/",
        {
            "incident": str(incident.id),
            "assets": [str(asset.id)],
            "assigned_name": "Scope Test",
            "assigned_organization": "Synthetic Agency",
            "driver_license_jurisdiction": "TX",
            "driver_license_number": "87654321",
        },
        format="json",
    )
    checkout_id = created.json()[0]["id"]

    client.force_authenticate(outsider)
    listing = client.get(f"/api/inventory-checkouts/?incident={incident.id}")
    detail = client.get(f"/api/inventory-checkouts/{checkout_id}/")

    assert listing.status_code == 403
    assert detail.status_code == 404
    assert "87654321" not in str(AuditEvent.objects.values_list("details", flat=True))


@pytest.mark.django_db
def test_programming_record_requires_codeplug_backup_attestation():
    manager = _user("programming-manager", Role.COMT)
    asset = Asset.objects.create(
        asset_id="RADIO-PROGRAM",
        category=Asset.Category.RADIO,
        created_by=manager,
    )
    client = APIClient()
    client.force_authenticate(manager)
    payload = {
        "asset": str(asset.id),
        "template_name": "Synthetic Template",
        "template_version": "v1",
        "programmed_at": datetime(2026, 8, 22, 12, 0, tzinfo=UTC).isoformat(),
        "codeplug_backup_saved": False,
        "backup_note": "Approved offline procedure",
    }

    rejected = client.post("/api/inventory-programming/", payload, format="json")
    payload["codeplug_backup_saved"] = True
    accepted = client.post("/api/inventory-programming/", payload, format="json")

    assert rejected.status_code == 400
    assert accepted.status_code == 201
    assert ProgrammingRecord.objects.get().confirmed_by == manager
    assert AuditEvent.objects.filter(action="inventory.codeplug_backup_attested").exists()


@pytest.mark.django_db
@override_settings(ICT_INVENTORY_ENCRYPTION_KEY=TEST_KEY)
def test_checkout_applies_versioned_issuer_input_limits():
    manager = _user("license-rule-manager", Role.COML)
    incident = _incident(manager)
    asset = Asset.objects.create(
        asset_id="RADIO-LICENSE-RULE",
        category=Asset.Category.RADIO,
        created_by=manager,
    )
    client = APIClient()
    client.force_authenticate(manager)
    payload = {
        "incident": str(incident.id),
        "assets": [str(asset.id)],
        "assigned_name": "License Rule Test",
        "assigned_organization": "Synthetic Agency",
        "driver_license_jurisdiction": "TX",
        "driver_license_number": "123456789",
    }

    too_long = client.post("/api/inventory-checkouts/", payload, format="json")
    payload["driver_license_jurisdiction"] = "ZZ"
    payload["driver_license_number"] = "12345678"
    unknown_issuer = client.post("/api/inventory-checkouts/", payload, format="json")

    assert too_long.status_code == 400
    assert "us-state-license-input-v1" in str(too_long.json())
    assert unknown_issuer.status_code == 400


@pytest.mark.django_db
@override_settings(ICT_INVENTORY_ENCRYPTION_KEY=TEST_KEY)
def test_multi_asset_checkout_and_operational_records_are_audited():
    manager = _user("operations-manager", Role.COML)
    incident = _incident(manager)
    radio = Asset.objects.create(
        asset_id="RADIO-MULTI", category=Asset.Category.RADIO, created_by=manager
    )
    battery = Asset.objects.create(
        asset_id="BATTERY-MULTI",
        category=Asset.Category.BATTERY,
        parent=radio,
        created_by=manager,
    )
    client = APIClient()
    client.force_authenticate(manager)

    duplicate_selection = client.post(
        "/api/inventory-checkouts/",
        {
            "incident": str(incident.id),
            "assets": [str(radio.id), str(radio.id)],
            "assigned_name": "Duplicate Asset Assignee",
            "assigned_organization": "Synthetic Agency",
            "driver_license_jurisdiction": "TX",
            "driver_license_number": "12345678",
        },
        format="json",
    )
    checked_out = client.post(
        "/api/inventory-checkouts/",
        {
            "incident": str(incident.id),
            "assets": [str(radio.id), str(battery.id)],
            "assigned_name": "Multi Asset Assignee",
            "assigned_organization": "Synthetic Agency",
            "point_of_contact": "Synthetic Supervisor",
            "phone_number": "555-0100",
            "mailing_address": "100 Test Street",
            "assignment_notes": "Synthetic assignment",
            "driver_license_jurisdiction": "TX",
            "driver_license_number": "12345678",
        },
        format="json",
    )
    maintenance = client.post(
        "/api/inventory-maintenance/",
        {
            "asset": str(radio.id),
            "kind": "calibration",
            "performed_at": "2026-08-23T01:00:00Z",
            "technician": "Synthetic Technician",
            "notes": "Bench calibration completed.",
            "return_to_service": True,
        },
        format="json",
    )
    charging = client.post(
        "/api/inventory-charging/",
        {
            "asset": str(battery.id),
            "started_at": "2026-08-23T01:00:00Z",
            "completed_at": "2026-08-23T03:00:00Z",
            "notes": "Synthetic charge cycle.",
        },
        format="json",
    )

    assert duplicate_selection.status_code == 400
    assert duplicate_selection.json()["assets"] == ["Each asset may be selected only once."]
    assert checked_out.status_code == 201
    assert len(checked_out.json()) == 2
    assert AssetCheckout.objects.filter(state=AssetCheckout.State.ACTIVE).count() == 2
    assert maintenance.status_code == 201
    assert charging.status_code == 201
    assert MaintenanceRecord.objects.get().recorded_by == manager
    assert ChargingRecord.objects.get().recorded_by == manager
    assert AuditEvent.objects.filter(action="inventory.maintenance_recorded").exists()
    assert AuditEvent.objects.filter(action="inventory.charging_recorded").exists()
