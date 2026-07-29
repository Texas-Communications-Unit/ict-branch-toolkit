import hashlib
import json

import pytest
from django.contrib.auth import get_user_model
from django.core import serializers as django_serializers
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.authtoken.models import Token

from apps.accounts.models import Role, UserRoleAssignment
from apps.audit.models import AuditEvent
from apps.extensions.models import ExtensionExecution, ExtensionInstallation
from apps.extensions.registry import (
    HANDLERS,
    SYNTHETIC_EXTENSION_KEY,
    SYNTHETIC_EXTENSION_VERSION,
)
from apps.extensions.services import (
    build_execution_package,
    canonical_digest,
    validate_execution_integrity,
)
from apps.incidents.models import Incident, IncidentMembership, OperationalPeriod
from apps.plans.models import Assignment, ICS205Plan, PlanRevision
from apps.plans.services import approve_revision


def auth_header(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {"HTTP_AUTHORIZATION": f"Token {token.key}"}


def user_with_role(username, role):
    user = get_user_model().objects.create_user(username, password="safe-test-password")
    UserRoleAssignment.objects.create(user=user, role=role)
    return user


def create_context(owner, suffix="BASE"):
    incident = Incident.objects.create(
        name=f"Synthetic Extension Exercise {suffix}",
        incident_number=f"SYN-EXT-{suffix}",
        created_by=owner,
    )
    IncidentMembership.objects.create(
        incident=incident,
        user=owner,
        role=Role.COML,
        assigned_by=owner,
    )
    period = OperationalPeriod.objects.create(
        incident=incident,
        name="Operational Period 1",
        starts_at="2026-07-28T08:00:00Z",
        ends_at="2026-07-28T20:00:00Z",
        created_by=owner,
    )
    plan = ICS205Plan.objects.create(
        incident=incident,
        operational_period=period,
        title="Synthetic Extension ICS-205",
        created_by=owner,
    )
    revision = PlanRevision.objects.create(plan=plan, number=1, created_by=owner)
    Assignment.objects.create(
        revision=revision,
        position=1,
        function="Command",
        channel_name="SYN CALL",
        assignment="Synthetic command",
        rx_frequency_hz=155_000_000,
        tx_frequency_hz=155_000_000,
        contact_name="Sensitive Test Contact",
        phone_numbers="555-0100",
        resource_snapshot={"type": "synthetic", "name": "SYN CALL"},
    )
    Assignment.objects.create(
        revision=revision,
        position=2,
        function="Operations",
        channel_name="SYN TAC",
        assignment="Synthetic operations",
        rx_frequency_hz=None,
        tx_frequency_hz=None,
        resource_snapshot={"type": "synthetic", "name": "SYN TAC"},
    )
    return incident, approve_revision(revision, owner)


def install_and_enable(client, administrator):
    headers = auth_header(administrator)
    installed = client.post(
        "/api/extensions/install/",
        {
            "extension_key": SYNTHETIC_EXTENSION_KEY,
            "contract_version": "1.0",
        },
        content_type="application/json",
        **headers,
    )
    assert installed.status_code == 201, installed.content
    enabled = client.post(
        f"/api/extensions/{SYNTHETIC_EXTENSION_KEY}/enable/",
        content_type="application/json",
        **headers,
    )
    assert enabled.status_code == 200, enabled.content
    return enabled.json()


@pytest.mark.django_db
def test_catalog_is_disabled_by_default_and_only_administrators_manage_installation(client):
    administrator = user_with_role("extension-admin", Role.ADMINISTRATOR)
    coml = user_with_role("extension-coml", Role.COML)

    catalog = client.get("/api/extensions/", **auth_header(coml))
    assert catalog.status_code == 200
    entry = catalog.json()[0]
    assert entry["manifest"]["key"] == SYNTHETIC_EXTENSION_KEY
    assert {item["kind"] for item in entry["manifest"]["capabilities"]} == {
        "tool",
        "report",
    }
    assert entry["installed"] is False
    assert entry["enabled"] is False
    assert entry["compatible"] is False
    assert "administrator" in entry["operator_message"].lower()

    forbidden = client.post(
        "/api/extensions/install/",
        {
            "extension_key": SYNTHETIC_EXTENSION_KEY,
            "contract_version": "1.0",
        },
        content_type="application/json",
        **auth_header(coml),
    )
    assert forbidden.status_code == 403

    installation = install_and_enable(client, administrator)
    assert installation["extension_version"] == SYNTHETIC_EXTENSION_VERSION
    assert installation["enabled"] is True
    assert AuditEvent.objects.filter(action="extension.installed").exists()
    assert AuditEvent.objects.filter(action="extension.enabled").exists()

    disabled = client.post(
        f"/api/extensions/{SYNTHETIC_EXTENSION_KEY}/disable/",
        content_type="application/json",
        **auth_header(administrator),
    )
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False


@pytest.mark.django_db
def test_tool_and_report_runs_are_deterministic_retained_redacted_and_audited(client):
    administrator = user_with_role("extension-run-admin", Role.ADMINISTRATOR)
    coml = user_with_role("extension-run-coml", Role.COML)
    incident, revision = create_context(coml, "RUN")
    install_and_enable(client, administrator)
    payload = {
        "extension_key": SYNTHETIC_EXTENSION_KEY,
        "contract_version": "1.0",
        "capability": "readiness-check",
        "incident": str(incident.id),
        "source_revision": str(revision.id),
        "inputs": {"minimum_assignment_count": 2},
    }

    first = client.post(
        "/api/extension-executions/",
        payload,
        content_type="application/json",
        **auth_header(coml),
    )
    second = client.post(
        "/api/extension-executions/",
        payload,
        content_type="application/json",
        **auth_header(coml),
    )
    assert first.status_code == second.status_code == 201
    first_body = first.json()
    second_body = second.json()
    assert first_body["status"] == "complete"
    assert first_body["output_classification"] == "decision_support"
    assert first_body["result_snapshot"]["assignment_count"] == 2
    assert first_body["result_snapshot"]["missing_frequency_count"] == 1
    assert first_body["result_snapshot"]["readiness_state"] == "attention"
    assert first_body["input_sha256"] == second_body["input_sha256"]
    assert first_body["result_sha256"] == second_body["result_sha256"]
    serialized = json.dumps(first_body)
    assert "Sensitive Test Contact" not in serialized
    assert "555-0100" not in serialized
    assert "155000000" not in serialized

    event = AuditEvent.objects.filter(action="extension.executed").latest("sequence")
    assert event.details["input_sha256"] == first_body["input_sha256"]
    assert event.details["result_sha256"] == first_body["result_sha256"]
    assert "result_snapshot" not in event.details

    execution = ExtensionExecution.objects.get(pk=first_body["id"])
    validate_execution_integrity(execution)
    execution.failure_code = "tamper"
    with pytest.raises(DjangoValidationError, match="immutable"):
        execution.save()
    with pytest.raises(DjangoValidationError, match="retained"):
        execution.delete()


@pytest.mark.django_db
def test_report_package_is_deterministic_audited_and_backup_serializable(client):
    administrator = user_with_role("extension-export-admin", Role.ADMINISTRATOR)
    coml = user_with_role("extension-export-coml", Role.COML)
    incident, revision = create_context(coml, "EXPORT")
    install_and_enable(client, administrator)
    created = client.post(
        "/api/extension-executions/",
        {
            "extension_key": SYNTHETIC_EXTENSION_KEY,
            "contract_version": "1.0",
            "capability": "readiness-report",
            "incident": str(incident.id),
            "source_revision": str(revision.id),
            "inputs": {"minimum_assignment_count": 1},
        },
        content_type="application/json",
        **auth_header(coml),
    )
    assert created.status_code == 201
    execution_id = created.json()["id"]

    first = client.get(
        f"/api/extension-executions/{execution_id}/export/",
        **auth_header(coml),
    )
    second = client.get(
        f"/api/extension-executions/{execution_id}/export/",
        **auth_header(coml),
    )
    assert first.status_code == second.status_code == 200
    assert first.content == second.content
    assert first["X-Content-SHA256"] == hashlib.sha256(first.content).hexdigest()
    package = json.loads(first.content)
    assert package["schema_version"] == "ict-extension-package-v1"
    assert package["source"]["revision_id"] == str(revision.id)
    assert package["output"]["classification"] == "decision_support"
    assert package["output"]["result"]["columns"] == [
        "Function",
        "Assignment count",
    ]
    assert AuditEvent.objects.filter(action="extension.exported").count() == 2

    execution = ExtensionExecution.objects.get(pk=execution_id)
    expected_package = build_execution_package(execution)
    installation_backup = django_serializers.serialize("json", [execution.installation])
    backup_json = django_serializers.serialize("json", [execution])
    backup_fields = json.loads(backup_json)[0]["fields"]
    assert backup_fields["input_sha256"] == execution.input_sha256
    assert backup_fields["result_sha256"] == execution.result_sha256
    assert canonical_digest(backup_fields["input_snapshot"]) == execution.input_sha256
    assert canonical_digest(backup_fields["result_snapshot"]) == execution.result_sha256

    ExtensionExecution.objects.filter(pk=execution.pk).delete()
    ExtensionInstallation.objects.filter(pk=execution.installation_id).delete()
    for restored_object in django_serializers.deserialize("json", installation_backup):
        restored_object.save()
    for restored_object in django_serializers.deserialize("json", backup_json):
        restored_object.save()
    restored = ExtensionExecution.objects.select_related("installation").get(pk=execution_id)
    validate_execution_integrity(restored)
    assert build_execution_package(restored) == expected_package


@pytest.mark.django_db
def test_contract_input_authorization_and_cross_incident_boundaries_fail_closed(client):
    administrator = user_with_role("extension-scope-admin", Role.ADMINISTRATOR)
    owner = user_with_role("extension-scope-owner", Role.COML)
    outsider = user_with_role("extension-scope-outsider", Role.COML)
    incident, revision = create_context(owner, "SCOPE")
    other_incident, _ = create_context(outsider, "OTHER")
    install_and_enable(client, administrator)
    base = {
        "extension_key": SYNTHETIC_EXTENSION_KEY,
        "contract_version": "1.0",
        "capability": "readiness-check",
        "incident": str(incident.id),
        "source_revision": str(revision.id),
        "inputs": {"minimum_assignment_count": 1},
    }

    incompatible = client.post(
        "/api/extension-executions/",
        {**base, "contract_version": "9.0"},
        content_type="application/json",
        **auth_header(owner),
    )
    assert incompatible.status_code == 400
    assert "Supported contracts" in json.dumps(incompatible.json())

    cross_incident = client.post(
        "/api/extension-executions/",
        {**base, "incident": str(other_incident.id)},
        content_type="application/json",
        **auth_header(outsider),
    )
    assert cross_incident.status_code == 400

    forbidden = client.post(
        "/api/extension-executions/",
        base,
        content_type="application/json",
        **auth_header(outsider),
    )
    assert forbidden.status_code == 403
    hidden = client.get(
        f"/api/extension-executions/?incident={incident.id}",
        **auth_header(outsider),
    )
    assert hidden.status_code == 200
    assert hidden.json()["results"] == []

    invalid_inputs = client.post(
        "/api/extension-executions/",
        {**base, "inputs": {"minimum_assignment_count": 0, "extra": "rejected"}},
        content_type="application/json",
        **auth_header(owner),
    )
    assert invalid_inputs.status_code == 400


@pytest.mark.django_db
def test_optional_extension_failure_is_retained_without_blocking_core_planning(client, monkeypatch):
    administrator = user_with_role("extension-failure-admin", Role.ADMINISTRATOR)
    owner = user_with_role("extension-failure-owner", Role.COML)
    incident, revision = create_context(owner, "FAILURE")
    install_and_enable(client, administrator)

    def fail_handler(source_revision, parameters):
        raise RuntimeError("Synthetic isolated failure")

    monkeypatch.setitem(
        HANDLERS,
        (SYNTHETIC_EXTENSION_KEY, "readiness-check"),
        fail_handler,
    )
    failed = client.post(
        "/api/extension-executions/",
        {
            "extension_key": SYNTHETIC_EXTENSION_KEY,
            "contract_version": "1.0",
            "capability": "readiness-check",
            "incident": str(incident.id),
            "source_revision": str(revision.id),
            "inputs": {"minimum_assignment_count": 1},
        },
        content_type="application/json",
        **auth_header(owner),
    )
    assert failed.status_code == 503
    assert failed.json()["status"] == "failed"
    assert failed.json()["failure_code"] == "extension_execution_failed"
    assert "Synthetic isolated failure" not in json.dumps(failed.json())
    assert ExtensionExecution.objects.filter(status="failed").exists()
    assert AuditEvent.objects.filter(action="extension.execution_failed").exists()

    health = client.get("/api/health/")
    assert health.status_code == 200
    incident_list = client.get("/api/incidents/", **auth_header(owner))
    assert incident_list.status_code == 200
    assert incident_list.json()["results"][0]["id"] == str(incident.id)


@pytest.mark.django_db
def test_catalog_and_execution_list_stay_inside_query_envelopes(client):
    administrator = user_with_role("extension-performance-admin", Role.ADMINISTRATOR)
    owner = user_with_role("extension-performance-owner", Role.COML)
    incident, revision = create_context(owner, "PERF")
    install_and_enable(client, administrator)
    client.post(
        "/api/extension-executions/",
        {
            "extension_key": SYNTHETIC_EXTENSION_KEY,
            "contract_version": "1.0",
            "capability": "readiness-check",
            "incident": str(incident.id),
            "source_revision": str(revision.id),
            "inputs": {"minimum_assignment_count": 1},
        },
        content_type="application/json",
        **auth_header(owner),
    )
    with CaptureQueriesContext(connection) as catalog_queries:
        response = client.get("/api/extensions/", **auth_header(owner))
    assert response.status_code == 200
    assert len(catalog_queries) <= 6

    with CaptureQueriesContext(connection) as list_queries:
        response = client.get(
            f"/api/extension-executions/?incident={incident.id}",
            **auth_header(owner),
        )
    assert response.status_code == 200
    assert len(list_queries) <= 8
