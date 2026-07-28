import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.authtoken.models import Token

from apps.resources.radioreference import (
    NORMALIZED_SCHEMA_VERSION,
    RadioReferenceContractError,
    parse_synthetic_soap_response,
    provider_status,
    validate_wsdl_url,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "radioreference" / "synthetic_response.xml"
RETRIEVED_AT = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)


def auth_header(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {"HTTP_AUTHORIZATION": f"Token {token.key}"}


def synthetic_payload(
    *,
    record_type: str = "frequency",
    fields: str = (
        "<rr:Name>Synthetic Dispatch</rr:Name><rr:FrequencyHz>155001000</rr:FrequencyHz>"
    ),
) -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" '
        'xmlns:rr="urn:tx-comu:synthetic:radioreference:v1">'
        "<soap:Body>"
        '<rr:ReferenceData sourceVersion="synthetic-contract-v1">'
        f'<rr:Record type="{record_type}" sourceId="SYN-RECORD-001">'
        f"{fields}"
        "</rr:Record>"
        "</rr:ReferenceData>"
        "</soap:Body>"
        "</soap:Envelope>"
    ).encode()


@pytest.mark.django_db
def test_provider_status_fails_closed_even_when_enablement_is_requested(client):
    assert client.get("/api/radioreference-provider/").status_code == 401
    user = get_user_model().objects.create_user(
        "synthetic-provider-reader",
        password="safe-test-password",
    )

    with override_settings(RADIOREFERENCE_ENABLED=True):
        response = client.get(
            "/api/radioreference-provider/",
            **auth_header(user),
        )

    assert response.status_code == 200
    assert response.json() == provider_status() | {"enabled_requested": True}
    payload = response.json()
    assert payload["available"] is False
    assert payload["mode"] == "disabled"
    assert payload["synthetic_contract_available"] is True
    assert payload["live_transport_implemented"] is False
    assert payload["developer_key_loaded"] is False
    assert payload["user_credentials_supported"] is False
    assert payload["credentials_retained"] is False
    assert payload["cache_supported"] is False
    assert payload["import_supported"] is False
    assert payload["export_supported"] is False
    assert "password" not in str(payload).lower()


def test_synthetic_soap_contract_normalizes_records_and_provenance():
    payload = FIXTURE_PATH.read_bytes()
    records = parse_synthetic_soap_response(
        payload,
        retrieval_scope="synthetic:browser-contract-test",
        retrieved_at=RETRIEVED_AT,
    )

    assert [record["record_type"] for record in records] == [
        "agency",
        "frequency",
        "trunked_system",
        "site",
        "talkgroup",
    ]
    assert {record["schema_version"] for record in records} == {NORMALIZED_SCHEMA_VERSION}
    assert all(record["provider"] == "radioreference" for record in records)
    assert all(record["synthetic"] is True for record in records)
    assert all(record["source_identifier"].startswith("SYN-") for record in records)
    assert all(record["source_version"] == "synthetic-contract-v1" for record in records)
    assert all(
        record["response_sha256"] == hashlib.sha256(payload).hexdigest() for record in records
    )
    assert all(record["raw_response_retained"] is False for record in records)
    assert all(record["credentials_retained"] is False for record in records)
    assert all(record["retrieval_scope"] == "synthetic:browser-contract-test" for record in records)
    assert all(record["retrieved_at"] == RETRIEVED_AT.isoformat() for record in records)

    frequency = records[1]
    assert frequency["rx_frequency_hz"] == 155_001_000
    assert frequency["tx_frequency_hz"] == 155_001_000
    site = records[3]
    assert site["latitude"] == "33.214500"
    assert site["longitude"] == "-97.133100"
    assert records[4]["talkgroup_id"] == 12_001


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b"", "must contain 1"),
        (b"<not-soap />", "SOAP Envelope"),
        (b"<soap:Envelope", "well-formed XML"),
        (
            b'<!DOCTYPE x [<!ENTITY secret SYSTEM "file:///etc/passwd">]><x />',
            "DTD and entity",
        ),
        (
            synthetic_payload(fields="<rr:Name>Synthetic Dispatch</rr:Name>"),
            "missing required fields",
        ),
        (
            synthetic_payload(
                fields=(
                    "<rr:Name>Synthetic Dispatch</rr:Name>"
                    "<rr:FrequencyHz>99999999999</rr:FrequencyHz>"
                )
            ),
            "FrequencyHz must be between",
        ),
        (
            synthetic_payload(
                record_type="talkgroup",
                fields=(
                    "<rr:Name>Synthetic Operations</rr:Name>"
                    "<rr:SystemName>Synthetic System</rr:SystemName>"
                    "<rr:TalkgroupId>999999999</rr:TalkgroupId>"
                ),
            ),
            "TalkgroupId must be between",
        ),
        (
            synthetic_payload(
                fields=(
                    "<rr:Name>Synthetic Dispatch</rr:Name>"
                    "<rr:FrequencyHz>155001000</rr:FrequencyHz>"
                    "<rr:Latitude>33</rr:Latitude>"
                )
            ),
            "frequency contains unsupported fields",
        ),
        (
            synthetic_payload(
                record_type="site",
                fields=(
                    "<rr:Name>Synthetic Site</rr:Name>"
                    "<rr:SiteName>Synthetic Site</rr:SiteName>"
                    "<rr:Latitude>91</rr:Latitude>"
                    "<rr:Longitude>-97</rr:Longitude>"
                ),
            ),
            "Latitude must be between",
        ),
    ],
)
def test_synthetic_parser_rejects_unsafe_or_invalid_contracts(payload, message):
    with pytest.raises(RadioReferenceContractError, match=message):
        parse_synthetic_soap_response(
            payload,
            retrieval_scope="synthetic:negative-contract-test",
            retrieved_at=RETRIEVED_AT,
        )


def test_synthetic_parser_rejects_oversize_scope_and_naive_timestamp():
    payload = synthetic_payload()
    with pytest.raises(RadioReferenceContractError, match="1 to 10 bytes"):
        parse_synthetic_soap_response(
            payload,
            retrieval_scope="synthetic:oversize-test",
            retrieved_at=RETRIEVED_AT,
            maximum_response_bytes=10,
        )
    with pytest.raises(RadioReferenceContractError, match="maximum_response_bytes"):
        parse_synthetic_soap_response(
            payload,
            retrieval_scope="synthetic:unsafe-limit-test",
            retrieved_at=RETRIEVED_AT,
            maximum_response_bytes=10_000_000,
        )
    with pytest.raises(RadioReferenceContractError, match="explicit synthetic scope"):
        parse_synthetic_soap_response(
            payload,
            retrieval_scope="operational:county",
            retrieved_at=RETRIEVED_AT,
        )
    with pytest.raises(RadioReferenceContractError, match="include a timezone"):
        parse_synthetic_soap_response(
            payload,
            retrieval_scope="synthetic:naive-time-test",
            retrieved_at=datetime(2026, 7, 28, 12, 0),
        )


@pytest.mark.parametrize(
    "value",
    [
        "http://api.example.invalid/wsdl",
        "https://user:password@example.invalid/wsdl",
        "https://example.invalid/wsdl#fragment",
        "not-a-url",
    ],
)
def test_wsdl_configuration_requires_safe_https_url(value):
    with pytest.raises(ValueError, match="must be an HTTPS URL"):
        validate_wsdl_url(value)


def test_wsdl_configuration_accepts_nonsecret_https_url():
    assert (
        validate_wsdl_url("https://api.example.invalid/service?wsdl=1")
        == "https://api.example.invalid/service?wsdl=1"
    )
