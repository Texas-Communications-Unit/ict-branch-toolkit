import json
import math
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import override_settings
from rest_framework.authtoken.models import Token

from apps.accounts.models import Role, UserRoleAssignment
from apps.audit.models import AuditEvent
from apps.deconfliction.models import DeconflictionAnalysis
from apps.deconfliction.rules import (
    ADJACENT_THRESHOLD_HZ,
    DISCLAIMER,
    RULE_SET_VERSION,
    evaluate,
)
from apps.incidents.models import Incident, IncidentMembership, OperationalPeriod
from apps.plans.models import Assignment, ICS205Plan, PlanRevision
from apps.plans.services import approve_revision
from apps.resources.models import ConventionalChannel, ResourceRelease, ResourceSource
from apps.sites.models import ManualRing, RadioSite, SiteAssignment


def auth_header(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {"HTTP_AUTHORIZATION": f"Token {token.key}"}


def user_with_role(username, role):
    user = get_user_model().objects.create_user(username, password="safe-test-password")
    UserRoleAssignment.objects.create(user=user, role=role)
    return user


def assignment_input(
    identifier,
    name,
    *,
    rx_frequency_hz,
    tx_frequency_hz,
    latitude="31.000000",
    longitude="-97.000000",
    radius_m=10_000,
    areas=True,
    rx_squelch="",
    tx_squelch="",
    resource_id=None,
):
    return {
        "id": identifier,
        "channel_name": name,
        "rx_frequency_hz": rx_frequency_hz,
        "tx_frequency_hz": tx_frequency_hz,
        "rx_squelch": rx_squelch,
        "tx_squelch": tx_squelch,
        "resource_id": resource_id,
        "areas": (
            [
                {
                    "site_id": f"site-{identifier}",
                    "site_name": f"Synthetic Site {identifier}",
                    "latitude": latitude,
                    "longitude": longitude,
                    "ring_type": "operational",
                    "radius_m": radius_m,
                    "label": "Synthetic area",
                }
            ]
            if areas
            else []
        ),
    }


@pytest.mark.parametrize(
    ("separation_hz", "longitude", "expected_rule"),
    [
        (0, "-97.000000", "RF-001"),
        (ADJACENT_THRESHOLD_HZ, "-97.000000", "RF-002"),
        (ADJACENT_THRESHOLD_HZ + 1, "-97.000000", None),
        (0, "-99.000000", None),
    ],
)
def test_cochannel_and_adjacent_boundary_table(separation_hz, longitude, expected_rule):
    first = assignment_input(
        "first",
        "SYN FIRST",
        rx_frequency_hz=155_000_000,
        tx_frequency_hz=155_000_000,
        tx_squelch="PL 100.0",
    )
    second = assignment_input(
        "second",
        "SYN SECOND",
        rx_frequency_hz=155_000_000 + separation_hz,
        tx_frequency_hz=155_000_000 + separation_hz,
        longitude=longitude,
        tx_squelch="NAC 293",
    )

    warnings = evaluate([first, second], [])
    frequency_rules = {warning["rule_id"] for warning in warnings if warning["rule_id"] <= "RF-002"}
    assert frequency_rules == ({expected_rule} if expected_rule else set())
    if expected_rule:
        warning = next(item for item in warnings if item["rule_id"] == expected_rule)
        assert warning["evidence"]["squelch_values_differ"] is True
        assert warning["disclaimer"] == DISCLAIMER
        assert warning["compared_inputs"][0]["tx_squelch"] == "PL 100.0"


def test_area_overlap_includes_exact_combined_radius_boundary():
    boundary_longitude = 20_000 / 6_371_008.8 * 180 / math.pi
    first = assignment_input(
        "first-boundary",
        "SYN FIRST BOUNDARY",
        rx_frequency_hz=155_000_000,
        tx_frequency_hz=155_000_000,
        latitude="0",
        longitude="0",
        radius_m=10_000,
    )
    second = assignment_input(
        "second-boundary",
        "SYN SECOND BOUNDARY",
        rx_frequency_hz=155_000_000,
        tx_frequency_hz=155_000_000,
        latitude="0",
        longitude=f"{boundary_longitude:.15f}",
        radius_m=10_000,
    )

    warning = next(item for item in evaluate([first, second], []) if item["rule_id"] == "RF-001")
    overlap = warning["evidence"]["area_overlap"]
    assert overlap["center_distance_m"] == overlap["combined_radius_m"] == 20_000
    assert overlap["overlap_test"] == "center_distance_m <= combined_radius_m"


def test_rule_table_detects_reversed_duplicate_missing_and_omitted_resources():
    assignments = [
        assignment_input(
            "repeater-a",
            "SYN REPEATER A",
            rx_frequency_hz=155_100_000,
            tx_frequency_hz=155_700_000,
            areas=False,
            resource_id="assigned-resource",
        ),
        assignment_input(
            "repeater-b",
            "SYN REPEATER B",
            rx_frequency_hz=155_700_000,
            tx_frequency_hz=155_100_000,
            areas=False,
        ),
        assignment_input(
            "duplicate",
            "SYN DUPLICATE NAME",
            rx_frequency_hz=155_100_000,
            tx_frequency_hz=155_700_000,
            areas=False,
        ),
        assignment_input(
            "missing",
            "SYN MISSING",
            rx_frequency_hz=156_000_000,
            tx_frequency_hz=None,
            areas=False,
        ),
    ]
    resources = [
        {
            "id": "assigned-resource",
            "identifier": "SYN-ASSIGNED",
            "name": "Synthetic assigned",
            "rx_frequency_hz": 155_100_000,
            "tx_frequency_hz": 155_700_000,
            "rx_squelch": "",
            "tx_squelch": "",
            "release": "synthetic-v1",
            "content_sha256": "a" * 64,
        },
        {
            "id": "omitted-resource",
            "identifier": "SYN-OMITTED",
            "name": "Synthetic omitted",
            "rx_frequency_hz": 158_000_000,
            "tx_frequency_hz": 158_000_000,
            "rx_squelch": "",
            "tx_squelch": "",
            "release": "synthetic-v1",
            "content_sha256": "a" * 64,
        },
    ]

    warnings = evaluate(assignments, resources)
    rule_ids = {warning["rule_id"] for warning in warnings}
    assert {"RF-003", "RF-004", "RF-005", "RF-006", "RF-007"} <= rule_ids
    omitted = next(warning for warning in warnings if warning["rule_id"] == "RF-006")
    assert omitted["evidence"]["resource_identifier"] == "SYN-OMITTED"
    missing = next(warning for warning in warnings if warning["rule_id"] == "RF-005")
    assert missing["evidence"]["missing_fields"] == ["tx_frequency_hz"]
    assert "will not invent" in missing["explanation"]


def create_analysis_context(owner, suffix="BASE"):
    incident = Incident.objects.create(
        name=f"Synthetic Deconfliction Exercise {suffix}",
        incident_number=f"SYN-DECON-{suffix}",
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
        title="Synthetic ICS-205",
        created_by=owner,
    )
    revision = PlanRevision.objects.create(plan=plan, number=1, created_by=owner)

    first = Assignment.objects.create(
        revision=revision,
        position=1,
        function="Command",
        channel_name="SYN CALL",
        assignment="Synthetic command",
        rx_frequency_hz=155_000_000,
        tx_frequency_hz=155_000_000,
        rx_squelch="PL 100.0",
        tx_squelch="PL 100.0",
        resource_snapshot={"type": "incident", "name": "SYN CALL"},
    )
    second = Assignment.objects.create(
        revision=revision,
        position=2,
        function="Operations",
        channel_name="SYN TAC",
        assignment="Synthetic operations",
        rx_frequency_hz=155_000_000,
        tx_frequency_hz=155_000_000,
        rx_squelch="NAC 293",
        tx_squelch="NAC 293",
        resource_snapshot={"type": "incident", "name": "SYN TAC"},
    )
    site = RadioSite.objects.create(
        incident=incident,
        name=f"Synthetic Command Site {suffix}",
        latitude=Decimal("31.000000"),
        longitude=Decimal("-97.000000"),
        coordinate_format=RadioSite.CoordinateFormat.DECIMAL,
        created_by=owner,
    )
    ManualRing.objects.create(
        site=site,
        ring_type=ManualRing.Type.OPERATIONAL,
        radius_m=10_000,
        label="Synthetic operating area",
    )
    SiteAssignment.objects.create(site=site, assignment=first)
    SiteAssignment.objects.create(site=site, assignment=second)
    revision = approve_revision(revision, owner)

    source = ResourceSource.objects.create(
        slug=f"synthetic-deconfliction-{suffix.lower()}",
        name=f"Synthetic Deconfliction Source {suffix}",
        source_type=ResourceSource.Type.SYNTHETIC,
    )
    release = ResourceRelease.objects.create(
        source=source,
        version="synthetic-v1",
        effective_status=ResourceRelease.Status.EFFECTIVE,
        content_sha256="a" * 64,
        permitted_use="Synthetic tests only.",
        imported_by=owner,
    )
    omitted_resource = ConventionalChannel.objects.create(
        release=release,
        identifier="SYN-OMITTED",
        name="Synthetic omitted active resource",
        rx_frequency_hz=158_000_000,
        tx_frequency_hz=158_000_000,
        mode=ConventionalChannel.Mode.ANALOG_FM,
    )
    return incident, revision, omitted_resource


@pytest.mark.django_db
def test_analysis_lifecycle_is_reproducible_audited_and_fail_closed(client):
    owner = user_with_role("deconfliction-owner", Role.COML)
    incident, revision, omitted_resource = create_analysis_context(owner)
    headers = auth_header(owner)

    status_response = client.get("/api/deconfliction-status/", **headers)
    assert status_response.status_code == 200
    assert status_response.json()["rule_set_version"] == RULE_SET_VERSION
    assert status_response.json()["approved_for_operational_use"] is False
    assert "never suppress" in status_response.json()["squelch_rule"]

    payload = {
        "incident": str(incident.id),
        "approved_revision": str(revision.id),
        "active_resources": [str(omitted_resource.id)],
    }
    response = client.post(
        "/api/deconfliction-analyses/",
        payload,
        content_type="application/json",
        **headers,
    )
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["status"] == "draft"
    assert body["rule_set_version"] == RULE_SET_VERSION
    assert body["input_snapshot"]["approved_revision"]["number"] == 1
    assert body["result_snapshot"]["input_sha256"] == body["input_sha256"]
    assert body["result_snapshot"]["warning_count"] == body["warning_count"]
    assert {"RF-001", "RF-004", "RF-006"} <= {
        warning["rule_id"] for warning in body["result_snapshot"]["warnings"]
    }

    repeated = client.post(
        "/api/deconfliction-analyses/",
        payload,
        content_type="application/json",
        **headers,
    )
    assert repeated.status_code == 201
    assert repeated.json()["input_sha256"] == body["input_sha256"]
    assert repeated.json()["result_sha256"] == body["result_sha256"]

    blocked = client.post(f"/api/deconfliction-analyses/{body['id']}/approve/", **headers)
    assert blocked.status_code == 400
    assert "practitioner gate" in json.dumps(blocked.json())

    created_event = AuditEvent.objects.filter(action="deconfliction_analysis.created").first()
    assert created_event
    assert created_event.details["input_sha256"] == body["input_sha256"]
    serialized_details = json.dumps(created_event.details)
    assert "155000000" not in serialized_details
    assert "31.000000" not in serialized_details


@pytest.mark.django_db
@override_settings(ICT_APPROVED_DECONFLICTION_RULESETS=[RULE_SET_VERSION])
def test_qualified_ruleset_gate_allows_approval_and_records_digest_only(client):
    owner = user_with_role("deconfliction-approver", Role.COML)
    incident, revision, omitted_resource = create_analysis_context(owner, "APPROVE")
    headers = auth_header(owner)
    created = client.post(
        "/api/deconfliction-analyses/",
        {
            "incident": str(incident.id),
            "approved_revision": str(revision.id),
            "active_resources": [str(omitted_resource.id)],
        },
        content_type="application/json",
        **headers,
    )
    approved = client.post(
        f"/api/deconfliction-analyses/{created.json()['id']}/approve/",
        **headers,
    )
    assert approved.status_code == 200, approved.content
    assert approved.json()["status"] == "approved"
    assert approved.json()["approved_by"] == owner.id
    event = AuditEvent.objects.get(action="deconfliction_analysis.approved")
    assert event.details["result_sha256"] == approved.json()["result_sha256"]
    assert "warnings" not in event.details


@pytest.mark.django_db
def test_analysis_rejects_draft_cross_incident_and_unauthorized_sources(client):
    owner = user_with_role("deconfliction-scope-owner", Role.COML)
    outsider = user_with_role("deconfliction-outsider", Role.READ_ONLY)
    incident, revision, omitted_resource = create_analysis_context(owner, "SCOPE")
    other_incident = Incident.objects.create(
        name="Other Synthetic Incident",
        incident_number="SYN-OTHER",
        created_by=owner,
    )
    IncidentMembership.objects.create(
        incident=other_incident,
        user=owner,
        role=Role.COML,
        assigned_by=owner,
    )
    headers = auth_header(owner)

    cross_incident = client.post(
        "/api/deconfliction-analyses/",
        {
            "incident": str(other_incident.id),
            "approved_revision": str(revision.id),
            "active_resources": [str(omitted_resource.id)],
        },
        content_type="application/json",
        **headers,
    )
    assert cross_incident.status_code == 400

    revision.status = PlanRevision.Status.DRAFT
    PlanRevision.objects.filter(pk=revision.pk).update(
        status=PlanRevision.Status.DRAFT,
        approved_by=None,
        approved_at=None,
    )
    draft = client.post(
        "/api/deconfliction-analyses/",
        {
            "incident": str(incident.id),
            "approved_revision": str(revision.id),
            "active_resources": [],
        },
        content_type="application/json",
        **headers,
    )
    assert draft.status_code == 400

    inaccessible = client.get(
        f"/api/deconfliction-analyses/?incident={incident.id}",
        **auth_header(outsider),
    )
    assert inaccessible.status_code == 200
    assert inaccessible.json()["results"] == []
    forbidden = client.post(
        "/api/deconfliction-analyses/",
        {
            "incident": str(incident.id),
            "approved_revision": str(revision.id),
            "active_resources": [],
        },
        content_type="application/json",
        **auth_header(outsider),
    )
    assert forbidden.status_code == 403


@pytest.mark.django_db
def test_analysis_models_are_retained_and_immutable(client):
    owner = user_with_role("deconfliction-immutable", Role.COML)
    incident, revision, omitted_resource = create_analysis_context(owner, "IMMUTABLE")
    created = client.post(
        "/api/deconfliction-analyses/",
        {
            "incident": str(incident.id),
            "approved_revision": str(revision.id),
            "active_resources": [str(omitted_resource.id)],
        },
        content_type="application/json",
        **auth_header(owner),
    )
    analysis = DeconflictionAnalysis.objects.get(pk=created.json()["id"])
    analysis.warning_count = 0
    with pytest.raises(DjangoValidationError, match="immutable"):
        analysis.save()
    with pytest.raises(DjangoValidationError, match="retained"):
        analysis.delete()
