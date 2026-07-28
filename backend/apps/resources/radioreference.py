from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlsplit
from xml.etree import ElementTree

from django.conf import settings
from django.utils import timezone

NORMALIZED_SCHEMA_VERSION = "radioreference-normalized-v1-synthetic"
SYNTHETIC_NAMESPACE = "urn:tx-comu:synthetic:radioreference:v1"
SOAP_NAMESPACES = {
    "http://schemas.xmlsoap.org/soap/envelope/",
    "http://www.w3.org/2003/05/soap-envelope",
}
RECORD_TYPES = {"agency", "frequency", "site", "talkgroup", "trunked_system"}
RECORD_FIELDS = {
    "AgencyName",
    "FrequencyHz",
    "Latitude",
    "Longitude",
    "Name",
    "SiteName",
    "SystemName",
    "TalkgroupId",
    "TxFrequencyHz",
}
RECORD_SHAPES = {
    "agency": {
        "required": {"Name"},
        "allowed": {"Name"},
    },
    "frequency": {
        "required": {"FrequencyHz", "Name"},
        "allowed": {"AgencyName", "FrequencyHz", "Name", "TxFrequencyHz"},
    },
    "site": {
        "required": {"Latitude", "Longitude", "Name", "SiteName"},
        "allowed": {"Latitude", "Longitude", "Name", "SiteName", "SystemName"},
    },
    "talkgroup": {
        "required": {"Name", "SystemName", "TalkgroupId"},
        "allowed": {"AgencyName", "Name", "SystemName", "TalkgroupId"},
    },
    "trunked_system": {
        "required": {"Name", "SystemName"},
        "allowed": {"AgencyName", "Name", "SystemName"},
    },
}
MAX_RECORDS = 500
ABSOLUTE_MAX_RESPONSE_BYTES = 5_242_880


class RadioReferenceContractError(ValueError):
    """Raised when a synthetic provider contract response fails closed."""


@dataclass(frozen=True)
class NormalizedRadioReferenceRecord:
    schema_version: str
    provider: str
    synthetic: bool
    record_type: str
    source_identifier: str
    source_version: str
    name: str
    agency_name: str | None
    system_name: str | None
    site_name: str | None
    rx_frequency_hz: int | None
    tx_frequency_hz: int | None
    talkgroup_id: int | None
    latitude: str | None
    longitude: str | None
    retrieval_scope: str
    retrieved_at: str
    response_sha256: str
    raw_response_retained: bool = False
    credentials_retained: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_wsdl_url(value: str) -> str:
    value = value.strip()
    if len(value) > 500:
        raise ValueError("RADIOREFERENCE_WSDL_URL cannot exceed 500 characters.")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise ValueError(
            "RADIOREFERENCE_WSDL_URL must be an HTTPS URL without embedded credentials "
            "or a fragment."
        )
    return value


def provider_status() -> dict[str, Any]:
    requested = bool(settings.RADIOREFERENCE_ENABLED)
    return {
        "provider": "radioreference",
        "contract_version": NORMALIZED_SCHEMA_VERSION,
        "enabled_requested": requested,
        "available": False,
        "mode": "disabled",
        "wsdl_url": settings.RADIOREFERENCE_WSDL_URL,
        "maximum_response_bytes": settings.RADIOREFERENCE_MAX_RESPONSE_BYTES,
        "synthetic_contract_available": True,
        "live_transport_implemented": False,
        "developer_key_loaded": False,
        "user_credentials_supported": False,
        "credentials_retained": False,
        "cache_supported": False,
        "import_supported": False,
        "export_supported": False,
        "warning": (
            "RadioReference live access remains disabled. Written licensing clarification, "
            "individual-user authentication design, security review, secret provisioning, "
            "and maintainer approval are required before any external request."
        ),
    }


def _qualified(namespace: str, local_name: str) -> str:
    return f"{{{namespace}}}{local_name}"


def _required_text(fields: dict[str, str], field: str) -> str:
    value = fields.get(field, "")
    if not value:
        raise RadioReferenceContractError(f"{field} is required.")
    return value


def _optional_integer(
    fields: dict[str, str],
    field: str,
    *,
    minimum: int,
    maximum: int,
) -> int | None:
    value = fields.get(field)
    if value is None:
        return None
    try:
        normalized = int(value)
    except ValueError as exc:
        raise RadioReferenceContractError(f"{field} must be a whole number.") from exc
    if normalized < minimum or normalized > maximum:
        raise RadioReferenceContractError(f"{field} must be between {minimum} and {maximum}.")
    return normalized


def _optional_coordinate(
    fields: dict[str, str],
    field: str,
    *,
    minimum: Decimal,
    maximum: Decimal,
) -> str | None:
    value = fields.get(field)
    if value is None:
        return None
    try:
        normalized = Decimal(value)
    except InvalidOperation as exc:
        raise RadioReferenceContractError(f"{field} must be a decimal value.") from exc
    if not normalized.is_finite() or normalized < minimum or normalized > maximum:
        raise RadioReferenceContractError(
            f"{field} must be between {format(minimum, 'f')} and {format(maximum, 'f')}."
        )
    return format(normalized, "f")


def _record_fields(record: ElementTree.Element) -> dict[str, str]:
    fields: dict[str, str] = {}
    for child in record:
        if not isinstance(child.tag, str) or not child.tag.startswith(f"{{{SYNTHETIC_NAMESPACE}}}"):
            raise RadioReferenceContractError("Record fields must use the synthetic namespace.")
        local_name = child.tag.removeprefix(f"{{{SYNTHETIC_NAMESPACE}}}")
        if local_name not in RECORD_FIELDS:
            raise RadioReferenceContractError(f"Unsupported synthetic field: {local_name}.")
        if child.attrib or list(child):
            raise RadioReferenceContractError(f"{local_name} must be a plain text field.")
        if local_name in fields:
            raise RadioReferenceContractError(f"{local_name} may appear only once.")
        value = (child.text or "").strip()
        if not value or len(value) > 300:
            raise RadioReferenceContractError(
                f"{local_name} must contain 1 to 300 visible characters."
            )
        fields[local_name] = value
    return fields


def _validate_record_shape(record_type: str, fields: dict[str, str]) -> None:
    shape = RECORD_SHAPES[record_type]
    missing = sorted(shape["required"] - fields.keys())
    if missing:
        raise RadioReferenceContractError(
            f"{record_type} is missing required fields: {', '.join(missing)}."
        )
    unexpected = sorted(fields.keys() - shape["allowed"])
    if unexpected:
        raise RadioReferenceContractError(
            f"{record_type} contains unsupported fields: {', '.join(unexpected)}."
        )
    if ("Latitude" in fields) != ("Longitude" in fields):
        raise RadioReferenceContractError("Latitude and Longitude must be supplied together.")


def parse_synthetic_soap_response(
    payload: bytes,
    *,
    retrieval_scope: str,
    retrieved_at: datetime,
    maximum_response_bytes: int | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(payload, bytes):
        raise RadioReferenceContractError("The SOAP response must be supplied as bytes.")
    maximum = (
        settings.RADIOREFERENCE_MAX_RESPONSE_BYTES
        if maximum_response_bytes is None
        else maximum_response_bytes
    )
    if not isinstance(maximum, int) or maximum < 1 or maximum > ABSOLUTE_MAX_RESPONSE_BYTES:
        raise RadioReferenceContractError(
            f"maximum_response_bytes must be 1 to {ABSOLUTE_MAX_RESPONSE_BYTES}."
        )
    if len(payload) == 0 or len(payload) > maximum:
        raise RadioReferenceContractError(f"The SOAP response must contain 1 to {maximum} bytes.")
    upper_payload = payload.upper()
    if b"<!DOCTYPE" in upper_payload or b"<!ENTITY" in upper_payload:
        raise RadioReferenceContractError("DTD and entity declarations are not permitted.")
    if not retrieval_scope.startswith("synthetic:") or len(retrieval_scope) > 160:
        raise RadioReferenceContractError(
            "Retrieval scope must be an explicit synthetic scope of 160 characters or fewer."
        )
    if timezone.is_naive(retrieved_at):
        raise RadioReferenceContractError("retrieved_at must include a timezone.")

    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError as exc:
        raise RadioReferenceContractError("The SOAP response is not well-formed XML.") from exc

    soap_namespace = next(
        (
            namespace
            for namespace in SOAP_NAMESPACES
            if root.tag == _qualified(namespace, "Envelope")
        ),
        None,
    )
    if soap_namespace is None:
        raise RadioReferenceContractError("The XML root must be a supported SOAP Envelope.")
    bodies = root.findall(_qualified(soap_namespace, "Body"))
    if len(bodies) != 1:
        raise RadioReferenceContractError("The SOAP Envelope must contain exactly one Body.")
    body_children = list(bodies[0])
    if len(body_children) != 1 or body_children[0].tag != _qualified(
        SYNTHETIC_NAMESPACE, "ReferenceData"
    ):
        raise RadioReferenceContractError(
            "The SOAP Body must contain the synthetic ReferenceData contract."
        )

    response = body_children[0]
    if set(response.attrib) != {"sourceVersion"}:
        raise RadioReferenceContractError("ReferenceData must declare only sourceVersion.")
    source_version = response.attrib["sourceVersion"].strip()
    if not source_version.startswith("synthetic-") or len(source_version) > 80:
        raise RadioReferenceContractError(
            "sourceVersion must identify an explicit synthetic source version."
        )

    records = list(response)
    if not records or len(records) > MAX_RECORDS:
        raise RadioReferenceContractError(
            f"ReferenceData must contain 1 to {MAX_RECORDS} synthetic records."
        )
    response_sha256 = hashlib.sha256(payload).hexdigest()
    retrieved_at_value = retrieved_at.isoformat()
    normalized_records: list[dict[str, Any]] = []
    seen_source_ids: set[str] = set()

    for record in records:
        if record.tag != _qualified(SYNTHETIC_NAMESPACE, "Record"):
            raise RadioReferenceContractError("ReferenceData may contain only Record elements.")
        if set(record.attrib) != {"sourceId", "type"}:
            raise RadioReferenceContractError("Record must declare only sourceId and type.")
        source_identifier = record.attrib["sourceId"].strip()
        record_type = record.attrib["type"].strip()
        if (
            not source_identifier.startswith("SYN-")
            or len(source_identifier) > 160
            or source_identifier in seen_source_ids
        ):
            raise RadioReferenceContractError(
                "Every sourceId must be unique, explicitly synthetic, and 160 characters or fewer."
            )
        if record_type not in RECORD_TYPES:
            raise RadioReferenceContractError(f"Unsupported record type: {record_type}.")
        seen_source_ids.add(source_identifier)
        fields = _record_fields(record)
        _validate_record_shape(record_type, fields)

        rx_frequency_hz = _optional_integer(
            fields,
            "FrequencyHz",
            minimum=1,
            maximum=10_000_000_000,
        )
        tx_frequency_hz = _optional_integer(
            fields,
            "TxFrequencyHz",
            minimum=1,
            maximum=10_000_000_000,
        )
        talkgroup_id = _optional_integer(
            fields,
            "TalkgroupId",
            minimum=0,
            maximum=16_777_215,
        )
        latitude = _optional_coordinate(
            fields,
            "Latitude",
            minimum=Decimal("-90"),
            maximum=Decimal("90"),
        )
        longitude = _optional_coordinate(
            fields,
            "Longitude",
            minimum=Decimal("-180"),
            maximum=Decimal("180"),
        )
        normalized_records.append(
            NormalizedRadioReferenceRecord(
                schema_version=NORMALIZED_SCHEMA_VERSION,
                provider="radioreference",
                synthetic=True,
                record_type=record_type,
                source_identifier=source_identifier,
                source_version=source_version,
                name=_required_text(fields, "Name"),
                agency_name=fields.get("AgencyName"),
                system_name=fields.get("SystemName"),
                site_name=fields.get("SiteName"),
                rx_frequency_hz=rx_frequency_hz,
                tx_frequency_hz=tx_frequency_hz,
                talkgroup_id=talkgroup_id,
                latitude=latitude,
                longitude=longitude,
                retrieval_scope=retrieval_scope,
                retrieved_at=retrieved_at_value,
                response_sha256=response_sha256,
            ).as_dict()
        )
    return normalized_records
