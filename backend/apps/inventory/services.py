from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.services import record_event

from .crypto import encrypt_value
from .driver_license_rules import RULESET_VERSION, normalize_and_validate
from .models import Asset, AssetCheckout, ProgrammingRecord


@transaction.atomic
def checkout_asset(
    *, asset, incident, assigned_name, assigned_organization, jurisdiction, number, actor
):
    asset = Asset.objects.select_for_update().get(pk=asset.pk)
    if asset.category != Asset.Category.RADIO:
        raise ValidationError({"asset": "Accountable checkout currently applies to radios."})
    if asset.status not in {Asset.Status.IN_SERVICE, Asset.Status.SPARE}:
        raise ValidationError({"asset": "This radio is not available for checkout."})
    issuer, normalized = normalize_and_validate(jurisdiction, number)
    checkout = AssetCheckout(
        incident=incident,
        asset=asset,
        assigned_name=assigned_name,
        assigned_organization=assigned_organization,
        driver_license_jurisdiction=issuer,
        driver_license_last_four=normalized[-4:],
        checked_out_by=actor,
    )
    checkout.driver_license_ciphertext = encrypt_value(
        normalized, context=checkout.driver_license_context
    )
    checkout.save()
    asset.status = Asset.Status.CHECKED_OUT
    asset.save(update_fields=["status", "updated_at"])
    record_event(
        actor=actor,
        action="inventory.asset_checked_out",
        target=checkout,
        details={
            "incident_id": str(incident.id),
            "asset_id": asset.asset_id,
            "jurisdiction": issuer,
            "input_rule_version": RULESET_VERSION,
        },
    )
    return checkout


@transaction.atomic
def return_asset(*, checkout, condition, hold_reason, actor):
    checkout = AssetCheckout.objects.select_for_update().select_related("asset").get(pk=checkout.pk)
    if checkout.state not in {AssetCheckout.State.ACTIVE, AssetCheckout.State.HOLD}:
        raise ValidationError("This checkout is already closed.")
    checkout.returned_by = actor
    checkout.returned_at = timezone.now()
    checkout.return_condition = condition
    if condition == AssetCheckout.ReturnCondition.NORMAL:
        checkout.state = AssetCheckout.State.RETURNED
        checkout.driver_license_ciphertext = ""
        checkout.driver_license_last_four = ""
        checkout.hold_reason = ""
        checkout.asset.status = Asset.Status.IN_SERVICE
        action = "inventory.asset_returned_license_deleted"
    else:
        checkout.state = AssetCheckout.State.HOLD
        checkout.hold_reason = hold_reason
        checkout.asset.status = (
            Asset.Status.MAINTENANCE
            if condition == AssetCheckout.ReturnCondition.DAMAGED
            else Asset.Status.CHECKED_OUT
        )
        action = "inventory.asset_returned_hold_created"
    checkout.save()
    checkout.asset.save(update_fields=["status", "updated_at"])
    record_event(
        actor=actor,
        action=action,
        target=checkout,
        details={
            "incident_id": str(checkout.incident_id),
            "asset_id": checkout.asset.asset_id,
            "condition": condition,
        },
    )
    return checkout


@transaction.atomic
def resolve_accountability_hold(*, checkout, asset_status, resolution_note, actor):
    checkout = AssetCheckout.objects.select_for_update().select_related("asset").get(pk=checkout.pk)
    if checkout.state != AssetCheckout.State.HOLD:
        raise ValidationError("Only an open accountability hold can be resolved.")
    checkout.state = AssetCheckout.State.RETURNED
    checkout.driver_license_ciphertext = ""
    checkout.driver_license_last_four = ""
    checkout.hold_resolved_by = actor
    checkout.hold_resolved_at = timezone.now()
    checkout.hold_resolution_note = resolution_note
    checkout.asset.status = asset_status
    checkout.save()
    checkout.asset.save(update_fields=["status", "updated_at"])
    record_event(
        actor=actor,
        action="inventory.accountability_hold_resolved_license_deleted",
        target=checkout,
        details={
            "incident_id": str(checkout.incident_id),
            "asset_id": checkout.asset.asset_id,
            "asset_status": asset_status,
        },
    )
    return checkout


def record_programming(*, actor, **values):
    if not values.get("codeplug_backup_saved"):
        raise ValidationError(
            {"codeplug_backup_saved": "Confirm the backup before completing the record."}
        )
    record = ProgrammingRecord.objects.create(confirmed_by=actor, **values)
    record_event(
        actor=actor,
        action="inventory.codeplug_backup_attested",
        target=record,
        details={
            "asset_id": record.asset.asset_id,
            "template_name": record.template_name,
            "template_version": record.template_version,
        },
    )
    return record
