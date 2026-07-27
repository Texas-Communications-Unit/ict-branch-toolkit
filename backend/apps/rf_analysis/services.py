import hashlib
import json
from copy import deepcopy
from decimal import Decimal, localcontext

from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import RFAnalysisInputSnapshot, SubscriberProfileVersion

VERSION_EDITABLE_FIELDS = (
    "tx_frequency_hz",
    "rx_frequency_hz",
    "transmitter_power_w",
    "effective_radiated_power_w",
    "erp_source",
    "receiver_sensitivity_dbm",
    "antenna_model",
    "antenna_gain_db",
    "antenna_gain_reference",
    "feed_line_type",
    "feed_line_length_m",
    "feed_line_loss_db",
    "additional_system_loss_db",
    "polarization",
    "frequency_band",
    "emission_designator",
    "emission_bandwidth_hz",
    "mounting_type",
    "antenna_center_agl_m",
    "antenna_center_amsl_m",
    "haat_m",
    "input_basis",
    "notes",
)
VERSION_SNAPSHOT_FIELDS = (*VERSION_EDITABLE_FIELDS, "erp_calculation_path")
CALCULATED_ERP_REQUIRED_FIELDS = (
    "transmitter_power_w",
    "antenna_gain_db",
    "feed_line_loss_db",
    "additional_system_loss_db",
)
NULLABLE_TEXT_FIELDS = (
    "antenna_model",
    "feed_line_type",
    "emission_designator",
    "notes",
)
ERP_QUANTUM = Decimal("0.000001")
DBI_TO_DBD_OFFSET = Decimal("2.150")


def _initial_field_value(field):
    if field.has_default():
        return field.get_default()
    if field.null:
        return None
    if field.empty_strings_allowed:
        return ""
    return None


def merged_version_values(instance, attrs):
    values = {}
    for field_name in VERSION_EDITABLE_FIELDS:
        if instance is not None:
            values[field_name] = getattr(instance, field_name)
        else:
            field = SubscriberProfileVersion._meta.get_field(field_name)
            values[field_name] = _initial_field_value(field)
    values.update(attrs)
    for field_name in NULLABLE_TEXT_FIELDS:
        value = values.get(field_name)
        if isinstance(value, str) and not value.strip():
            values[field_name] = None
    return values


def calculate_erp(values):
    missing = [field for field in CALCULATED_ERP_REQUIRED_FIELDS if values.get(field) is None]
    gain_reference = values.get(
        "antenna_gain_reference",
        SubscriberProfileVersion.AntennaGainReference.UNKNOWN,
    )
    if gain_reference not in {
        SubscriberProfileVersion.AntennaGainReference.DBI,
        SubscriberProfileVersion.AntennaGainReference.DBD,
    }:
        missing.append("antenna_gain_reference")
    if missing:
        raise ValidationError(
            {
                "erp_source": (
                    "Calculated ERP requires explicit transmitter power, antenna gain and "
                    "gain reference, feed-line loss, and additional system loss. Zero losses "
                    f"must be entered as zero. Missing: {', '.join(sorted(missing))}."
                )
            }
        )

    transmitter_power_w = Decimal(values["transmitter_power_w"])
    entered_gain_db = Decimal(values["antenna_gain_db"])
    feed_line_loss_db = Decimal(values["feed_line_loss_db"])
    additional_system_loss_db = Decimal(values["additional_system_loss_db"])
    gain_dbd = (
        entered_gain_db - DBI_TO_DBD_OFFSET
        if gain_reference == SubscriberProfileVersion.AntennaGainReference.DBI
        else entered_gain_db
    )
    net_gain_db = gain_dbd - feed_line_loss_db - additional_system_loss_db
    total_loss_db = feed_line_loss_db + additional_system_loss_db
    with localcontext() as context:
        context.prec = 28
        antenna_input_power_w = transmitter_power_w * (
            Decimal(10) ** (-total_loss_db / Decimal(10))
        )
        result = (antenna_input_power_w * (Decimal(10) ** (gain_dbd / Decimal(10)))).quantize(
            ERP_QUANTUM
        )
        antenna_input_power_display = antenna_input_power_w.quantize(ERP_QUANTUM)

    return result, {
        "method": "calculated",
        "method_version": "erp-v1-provisional",
        "formula": (
            "antenna_input_power_w = transmitter_power_w * "
            "10 ** (-(feed_line_loss_db + additional_system_loss_db) / 10); "
            "erp_w = antenna_input_power_w * 10 ** (antenna_gain_dbd / 10)"
        ),
        "components": {
            "transmitter_power_w": format(transmitter_power_w, "f"),
            "antenna_gain_entered_db": format(entered_gain_db, "f"),
            "antenna_gain_reference": gain_reference,
            "dbi_to_dbd_offset_db": (
                format(DBI_TO_DBD_OFFSET, "f")
                if gain_reference == SubscriberProfileVersion.AntennaGainReference.DBI
                else "0.000"
            ),
            "antenna_gain_dbd": format(gain_dbd, "f"),
            "feed_line_loss_db": format(feed_line_loss_db, "f"),
            "additional_system_loss_db": format(additional_system_loss_db, "f"),
            "total_loss_db": format(total_loss_db, "f"),
            "antenna_input_power_w": format(antenna_input_power_display, "f"),
            "net_gain_db": format(net_gain_db, "f"),
        },
        "result_effective_radiated_power_w": format(result, "f"),
    }


def normalize_erp(values):
    normalized = dict(values)
    source = normalized.get("erp_source", SubscriberProfileVersion.ERPSource.UNKNOWN)
    supplied_erp = normalized.get("effective_radiated_power_w")

    if source == SubscriberProfileVersion.ERPSource.CALCULATED:
        calculated, path = calculate_erp(normalized)
        normalized["effective_radiated_power_w"] = calculated
        normalized["erp_calculation_path"] = path
    elif source == SubscriberProfileVersion.ERPSource.ENTERED:
        if supplied_erp is None:
            raise ValidationError(
                {
                    "effective_radiated_power_w": (
                        "Entered ERP requires an effective radiated power value."
                    )
                }
            )
        normalized["erp_calculation_path"] = {"method": "entered"}
    else:
        if supplied_erp is not None:
            raise ValidationError(
                {
                    "effective_radiated_power_w": (
                        "Unknown ERP source requires effective radiated power to be null."
                    )
                }
            )
        normalized["erp_calculation_path"] = {"method": "unknown"}
    notes = normalized.get("notes")
    if source == SubscriberProfileVersion.ERPSource.ENTERED and not (notes and notes.strip()):
        raise ValidationError(
            {"notes": "Entered ERP requires notes describing the source or method."}
        )
    if normalized.get("input_basis") == SubscriberProfileVersion.InputBasis.MIXED and not (
        notes and notes.strip()
    ):
        raise ValidationError(
            {"notes": "Mixed recorded facts and modeled assumptions require explanatory notes."}
        )
    return normalized


def normalize_version_attrs(instance, attrs):
    for field_name in NULLABLE_TEXT_FIELDS:
        value = attrs.get(field_name)
        if isinstance(value, str) and not value.strip():
            attrs[field_name] = None
    merged = merged_version_values(instance, attrs)
    normalized = normalize_erp(merged)
    attrs["effective_radiated_power_w"] = normalized["effective_radiated_power_w"]
    attrs["erp_calculation_path"] = normalized["erp_calculation_path"]
    return attrs


def _snapshot_value(version, field_name):
    value = getattr(version, field_name)
    if value is None:
        return None
    field = version._meta.get_field(field_name)
    if hasattr(field, "decimal_places"):
        return f"{value:.{field.decimal_places}f}"
    if field_name == "erp_calculation_path":
        return deepcopy(value)
    return value


def canonical_input_snapshot(version):
    return {
        "schema_version": 1,
        "profile": {
            "id": str(version.profile_id),
            "incident": str(version.profile.incident_id),
            "name": version.profile.name,
            "profile_type": version.profile.profile_type,
            "description": version.profile.description,
        },
        "profile_version": {
            "id": str(version.id),
            "number": version.number,
        },
        "inputs": {
            field_name: _snapshot_value(version, field_name)
            for field_name in VERSION_SNAPSHOT_FIELDS
        },
    }


def snapshot_digest(snapshot):
    canonical = json.dumps(
        snapshot,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@transaction.atomic
def copy_version(version, actor):
    if version.status != SubscriberProfileVersion.Status.APPROVED:
        raise ValidationError("Only an approved subscriber profile version can be copied.")
    if version.profile.archived_at:
        raise ValidationError("Archived subscriber profiles cannot be changed.")
    if version.profile.versions.filter(status=SubscriberProfileVersion.Status.DRAFT).exists():
        raise ValidationError("This subscriber profile already has an editable draft.")
    next_number = (
        version.profile.versions.aggregate(max_number=Max("number"))["max_number"] or 0
    ) + 1
    copied_values = {
        field_name: deepcopy(getattr(version, field_name)) for field_name in VERSION_SNAPSHOT_FIELDS
    }
    return SubscriberProfileVersion.objects.create(
        profile=version.profile,
        number=next_number,
        created_by=actor,
        **copied_values,
    )


@transaction.atomic
def approve_version(version, actor):
    if version.status != SubscriberProfileVersion.Status.DRAFT:
        raise ValidationError("Only a draft subscriber profile version can be approved.")
    if version.profile.archived_at:
        raise ValidationError("Archived subscriber profiles cannot be approved.")

    normalized = normalize_erp(merged_version_values(version, {}))
    for field_name in NULLABLE_TEXT_FIELDS:
        setattr(version, field_name, normalized[field_name])
    version.effective_radiated_power_w = normalized["effective_radiated_power_w"]
    version.erp_calculation_path = normalized["erp_calculation_path"]
    version.full_clean()
    version.save(
        update_fields=[
            *NULLABLE_TEXT_FIELDS,
            "effective_radiated_power_w",
            "erp_calculation_path",
            "updated_at",
        ]
    )
    version.refresh_from_db()

    snapshot = canonical_input_snapshot(version)
    version.status = SubscriberProfileVersion.Status.APPROVED
    version.input_snapshot = snapshot
    version.input_sha256 = snapshot_digest(snapshot)
    version.approved_by = actor
    version.approved_at = timezone.now()
    version.save(
        update_fields=[
            "status",
            "input_snapshot",
            "input_sha256",
            "approved_by",
            "approved_at",
            "updated_at",
        ]
    )
    return version


@transaction.atomic
def create_analysis_snapshot(version, *, label, actor):
    if version.status != SubscriberProfileVersion.Status.APPROVED:
        raise ValidationError("RF analysis input snapshots require an approved profile version.")
    if not version.input_snapshot or not version.input_sha256:
        raise ValidationError("The approved profile version is missing its canonical snapshot.")
    return RFAnalysisInputSnapshot.objects.create(
        incident=version.profile.incident,
        profile_version=version,
        label=label,
        input_snapshot=deepcopy(version.input_snapshot),
        input_sha256=version.input_sha256,
        created_by=actor,
        approved_by=version.approved_by,
        approved_at=version.approved_at,
    )


@transaction.atomic
def archive_analysis_snapshot(snapshot):
    if snapshot.archived_at:
        raise ValidationError("This RF analysis input snapshot is already archived.")
    archived_at = timezone.now()
    RFAnalysisInputSnapshot.objects.filter(pk=snapshot.pk, archived_at__isnull=True).update(
        archived_at=archived_at
    )
    snapshot.refresh_from_db()
    return snapshot
