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
from apps.deconfliction.models import (
    DeconflictionAnalysis,
    DeconflictionFindingDisposition,
)
from apps.deconfliction.rules import (
    CLOSE_FREQUENCY_THRESHOLD_HZ,
    DISCLAIMER,
    RULE_SET_VERSION,
    evaluate,
)
from apps.deconfliction.services import canonical_digest
from apps.incidents.models import Incident, IncidentMembership, OperationalPeriod
from apps.plans.models import Assignment, ICS205Plan, PlanRevision
from apps.plans.services import approve_revision
from apps.resources.models import ConventionalChannel, ResourceRelease, ResourceSource
from apps.rf_analysis.models import SubscriberProfile, SubscriberProfileVersion
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
    operating_classification="fixed_pair",
    technology_subtype="",
    expected_access_code_source=None,
):
    return {
        "id": identifier,
        "position": 1,
        "function": "Synthetic function",
        "channel_name": name,
        "assignment": "Synthetic assignment",
        "operating_classification": operating_classification,
        "technology_subtype": technology_subtype,
        "rx_frequency_hz": rx_frequency_hz,
        "tx_frequency_hz": tx_frequency_hz,
        "rx_squelch": rx_squelch,
        "tx_squelch": tx_squelch,
        "expected_access_code_source": expected_access_code_source,
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
        (CLOSE_FREQUENCY_THRESHOLD_HZ, "-97.000000", "RF-002"),
        (CLOSE_FREQUENCY_THRESHOLD_HZ + 1, "-97.000000", None),
        (0, "-99.000000", None),
    ],
)
def test_cochannel_and_close_frequency_boundary_table(
    separation_hz,
    longitude,
    expected_rule,
):
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

    evaluation = evaluate([first, second])
    frequency_rules = {
        warning["rule_id"]
        for warning in evaluation["warnings"]
        if warning["rule_id"] in {"RF-001", "RF-002"}
    }
    assert frequency_rules == ({expected_rule} if expected_rule else set())
    if expected_rule:
        warning = next(item for item in evaluation["warnings"] if item["rule_id"] == expected_rule)
        assert warning["evidence"]["access_code_values_differ"] is True
        assert warning["blocking"] is False
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

    warning = next(
        item for item in evaluate([first, second])["warnings"] if item["rule_id"] == "RF-001"
    )
    overlap = warning["evidence"]["area_overlap"]
    assert overlap["center_distance_m"] == overlap["combined_radius_m"] == 20_000
    assert overlap["overlap_test"] == "center_distance_m <= combined_radius_m"
    assert overlap["boundary_is_inclusive"] is True


def test_reversed_duplicate_and_scope_status_table():
    assignments = [
        assignment_input(
            "repeater-a",
            "SYN REPEATER A",
            rx_frequency_hz=155_100_000,
            tx_frequency_hz=155_700_000,
            areas=False,
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
            "named",
            "SYN TALKGROUP",
            rx_frequency_hz=None,
            tx_frequency_hz=None,
            areas=False,
            operating_classification="named_system",
            technology_subtype="trunked_talkgroup",
        ),
    ]

    evaluation = evaluate(assignments)
    rule_ids = {warning["rule_id"] for warning in evaluation["warnings"]}
    assert {"RF-003", "RF-004"} <= rule_ids
    assert "RF-005" not in rule_ids
    assert "RF-006" not in rule_ids
    area_status = next(
        status for status in evaluation["analysis_statuses"] if status["status_id"] == "RF-007"
    )
    assert area_status["outcome"] == "not_evaluated"
    assert area_status["affected_rule_ids"] == ["RF-001", "RF-002"]
    not_applicable = next(
        status
        for status in evaluation["analysis_statuses"]
        if status["status_id"] == "RF-STATUS-001" and status["assignment"]["id"] == "named"
    )
    assert not_applicable["outcome"] == "not_applicable"


def test_directional_access_code_mismatch_and_unknown_expected_values():
    assignment = assignment_input(
        "access",
        "SYN ACCESS",
        rx_frequency_hz=155_000_000,
        tx_frequency_hz=155_000_000,
        rx_squelch="NAC 293",
        tx_squelch="PL 100.0",
        expected_access_code_source={
            "source_type": "selected_versioned_channel_definition",
            "source_id": "synthetic-channel",
            "source_name": "Synthetic channel",
            "source_revision": "synthetic-v1",
            "source_content_sha256": "a" * 64,
            "rx": "NAC 293",
            "tx": "PL 123.0",
        },
    )

    evaluation = evaluate([assignment])
    mismatch = next(warning for warning in evaluation["warnings"] if warning["rule_id"] == "RF-008")
    assert mismatch["severity"] == "critical"
    assert mismatch["blocking"] is False
    assert mismatch["evidence"]["mismatches"] == [
        {
            "direction": "tx",
            "entered_value": "PL 100.0",
            "expected_value": "PL 123.0",
            "comparison": "normalized case-insensitive literal comparison",
        }
    ]

    assignment["expected_access_code_source"]["tx"] = ""
    unknown = evaluate([assignment])
    assert not any(warning["rule_id"] == "RF-008" for warning in unknown["warnings"])
    status = next(
        item for item in unknown["analysis_statuses"] if item["status_id"] == "RF-STATUS-002"
    )
    assert status["evidence"]["unevaluated_directions"] == ["tx"]


def test_access_code_comparison_uses_only_the_one_way_operating_direction():
    transmit_only = assignment_input(
        "transmit-only-access",
        "SYN BROADCAST",
        rx_frequency_hz=None,
        tx_frequency_hz=155_000_000,
        rx_squelch="",
        tx_squelch="NAC 293",
        operating_classification="transmit_only",
        expected_access_code_source={
            "source_type": "selected_versioned_channel_definition",
            "source_id": "synthetic-channel",
            "source_name": "Synthetic channel",
            "source_revision": "synthetic-v1",
            "source_content_sha256": "a" * 64,
            "rx": "PL 100.0",
            "tx": "NAC 293",
        },
    )
    receive_only = assignment_input(
        "receive-only-access",
        "SYN MONITOR",
        rx_frequency_hz=155_000_000,
        tx_frequency_hz=None,
        rx_squelch="PL 100.0",
        tx_squelch="",
        operating_classification="receive_only",
        expected_access_code_source={
            "source_type": "approved_subscriber_programming_profile",
            "source_id": "synthetic-profile",
            "source_name": "Synthetic profile",
            "source_revision": "1",
            "source_content_sha256": "b" * 64,
            "rx": "PL 100.0",
            "tx": "NAC 293",
        },
    )

    evaluation = evaluate([transmit_only, receive_only])
    assert not any(warning["rule_id"] == "RF-008" for warning in evaluation["warnings"])
    assert not any(
        status["status_id"] == "RF-STATUS-002" for status in evaluation["analysis_statuses"]
    )


def create_analysis_context(owner, suffix="BASE", *, include_access_sources=False):
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

    conventional_channel = None
    subscriber_profile_version = None
    if include_access_sources:
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
            permitted_use="Synthetic automated test fixture only.",
            imported_by=owner,
        )
        conventional_channel = ConventionalChannel.objects.create(
            release=release,
            identifier=f"SYN-{suffix}",
            name="SYN CALL",
            rx_frequency_hz=155_000_000,
            tx_frequency_hz=155_000_000,
            mode=ConventionalChannel.Mode.P25,
            rx_squelch="NAC 293",
            tx_squelch="NAC 293",
        )
        subscriber_profile = SubscriberProfile.objects.create(
            incident=incident,
            name=f"Synthetic Subscriber Profile {suffix}",
            profile_type=SubscriberProfile.ProfileType.PORTABLE,
            created_by=owner,
        )
        subscriber_profile_version = SubscriberProfileVersion.objects.create(
            profile=subscriber_profile,
            number=1,
            status=SubscriberProfileVersion.Status.APPROVED,
            rx_access_code="PL 100.0",
            tx_access_code="PL 100.0",
            input_sha256="b" * 64,
            created_by=owner,
            approved_by=owner,
            approved_at="2026-07-29T12:00:00Z",
        )

    first = Assignment.objects.create(
        revision=revision,
        position=1,
        function="Command",
        channel_name="SYN CALL",
        assignment="Synthetic command",
        operating_classification=Assignment.OperatingClassification.FIXED_PAIR,
        rx_frequency_hz=155_000_000,
        tx_frequency_hz=155_000_000,
        rx_squelch="PL 100.0",
        tx_squelch="PL 100.0",
        conventional_channel=conventional_channel,
        subscriber_profile_version=subscriber_profile_version,
        resource_snapshot={"type": "incident", "name": "SYN CALL"},
    )
    second = Assignment.objects.create(
        revision=revision,
        position=2,
        function="Operations",
        channel_name="SYN TAC",
        assignment="Synthetic operations",
        operating_classification=Assignment.OperatingClassification.FIXED_PAIR,
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
    return incident, revision


@pytest.mark.django_db
def test_analysis_freezes_access_code_source_hierarchy_and_uses_channel_first(client):
    owner = user_with_role("deconfliction-access-source", Role.COML)
    incident, revision = create_analysis_context(
        owner,
        "ACCESS-SOURCE",
        include_access_sources=True,
    )
    response = client.post(
        "/api/deconfliction-analyses/",
        {
            "incident": str(incident.id),
            "approved_revision": str(revision.id),
        },
        content_type="application/json",
        **auth_header(owner),
    )
    assert response.status_code == 201, response.content

    assignment = response.json()["input_snapshot"]["assignments"][0]
    assert assignment["expected_access_code_source"]["source_type"] == (
        "selected_versioned_channel_definition"
    )
    assert [source["source_type"] for source in assignment["available_access_code_sources"]] == [
        "selected_versioned_channel_definition",
        "approved_subscriber_programming_profile",
    ]
    mismatch = next(
        warning
        for warning in response.json()["result_snapshot"]["warnings"]
        if warning["rule_id"] == "RF-008"
        and warning["compared_inputs"][0]["id"] == assignment["id"]
    )
    assert mismatch["evidence"]["comparison_source"]["source_type"] == (
        "selected_versioned_channel_definition"
    )
    assert {item["direction"] for item in mismatch["evidence"]["mismatches"]} == {
        "rx",
        "tx",
    }


@pytest.mark.django_db
def test_analysis_lifecycle_is_reproducible_audited_and_fail_closed(client):
    owner = user_with_role("deconfliction-owner", Role.COML)
    incident, revision = create_analysis_context(owner)
    headers = auth_header(owner)

    status_response = client.get("/api/deconfliction-status/", **headers)
    assert status_response.status_code == 200
    assert status_response.json()["rule_set_version"] == RULE_SET_VERSION
    assert status_response.json()["approved_for_operational_use"] is False
    assert status_response.json()["close_frequency_threshold_hz"] == 12_500
    assert "never suppress" in status_response.json()["squelch_rule"]

    payload = {
        "incident": str(incident.id),
        "approved_revision": str(revision.id),
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
    assert body["input_snapshot"]["schema_version"] == "rf-deconfliction-input-v2"
    assert "selected_active_resources" not in body["input_snapshot"]
    assert body["result_snapshot"]["input_sha256"] == body["input_sha256"]
    assert body["result_snapshot"]["warning_count"] == body["warning_count"]
    assert {"RF-001", "RF-004"} <= {
        warning["rule_id"] for warning in body["result_snapshot"]["warnings"]
    }
    assert body["result_snapshot"]["analysis_status_count"] == 2
    assert {status["status_id"] for status in body["result_snapshot"]["analysis_statuses"]} == {
        "RF-STATUS-002"
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
    assert created_event.details["analysis_status_count"] == 2
    serialized_details = json.dumps(created_event.details)
    assert "155000000" not in serialized_details
    assert "31.000000" not in serialized_details
    assert "PL 100.0" not in serialized_details
    assert "NAC 293" not in serialized_details
    assert "Synthetic operating area" not in serialized_details


@pytest.mark.django_db
def test_finding_dispositions_are_append_only_incident_scoped_and_audited(client):
    owner = user_with_role("deconfliction-disposition", Role.COML)
    incident, revision = create_analysis_context(owner, "DISPOSITION")
    headers = auth_header(owner)
    created = client.post(
        "/api/deconfliction-analyses/",
        {
            "incident": str(incident.id),
            "approved_revision": str(revision.id),
        },
        content_type="application/json",
        **headers,
    )
    finding = next(
        warning
        for warning in created.json()["result_snapshot"]["warnings"]
        if warning["rule_id"] == "RF-001"
    )

    recorded = client.post(
        f"/api/deconfliction-analyses/{created.json()['id']}/dispositions/",
        {
            "finding_key": finding["finding_key"],
            "disposition": "reviewed_no_change",
            "explanation": "Synthetic exercise relationship reviewed.",
        },
        content_type="application/json",
        **headers,
    )
    assert recorded.status_code == 201, recorded.content
    assert recorded.json()["rule_id"] == "RF-001"
    assert recorded.json()["finding_key"] == finding["finding_key"]

    follow_up = client.post(
        f"/api/deconfliction-analyses/{created.json()['id']}/dispositions/",
        {
            "finding_key": finding["finding_key"],
            "disposition": "plan_change_required",
            "explanation": "Later synthetic review requires a revised plan.",
        },
        content_type="application/json",
        **headers,
    )
    assert follow_up.status_code == 201
    assert DeconflictionFindingDisposition.objects.count() == 2

    first = DeconflictionFindingDisposition.objects.first()
    first.explanation = "Forbidden rewrite"
    with pytest.raises(DjangoValidationError, match="append-only"):
        first.save()
    with pytest.raises(DjangoValidationError, match="retained"):
        first.delete()

    event = AuditEvent.objects.filter(action="deconfliction_finding.disposition_recorded").latest(
        "occurred_at"
    )
    assert event.details["finding_key"] == finding["finding_key"]
    assert "explanation" not in event.details
    assert "Later synthetic review requires a revised plan." not in json.dumps(event.details)

    invalid = client.post(
        f"/api/deconfliction-analyses/{created.json()['id']}/dispositions/",
        {
            "finding_key": "a" * 64,
            "disposition": "reviewed_no_change",
            "explanation": "Synthetic invalid finding.",
        },
        content_type="application/json",
        **headers,
    )
    assert invalid.status_code == 400


@pytest.mark.django_db
@override_settings(ICT_APPROVED_DECONFLICTION_RULESETS=[RULE_SET_VERSION])
def test_qualified_ruleset_gate_allows_approval_and_records_digest_only(client):
    owner = user_with_role("deconfliction-approver", Role.COML)
    incident, revision = create_analysis_context(owner, "APPROVE")
    headers = auth_header(owner)
    created = client.post(
        "/api/deconfliction-analyses/",
        {
            "incident": str(incident.id),
            "approved_revision": str(revision.id),
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
    incident, revision = create_analysis_context(owner, "SCOPE")
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
        },
        content_type="application/json",
        **headers,
    )
    assert cross_incident.status_code == 400

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
        },
        content_type="application/json",
        **auth_header(outsider),
    )
    assert forbidden.status_code == 403


@pytest.mark.django_db
def test_analysis_models_are_retained_and_immutable(client):
    owner = user_with_role("deconfliction-immutable", Role.COML)
    incident, revision = create_analysis_context(owner, "IMMUTABLE")
    created = client.post(
        "/api/deconfliction-analyses/",
        {
            "incident": str(incident.id),
            "approved_revision": str(revision.id),
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


@pytest.mark.django_db
def test_analysis_api_denies_mutation_and_preserves_legacy_v1_history(client):
    owner = user_with_role("deconfliction-retention", Role.COML)
    incident, revision = create_analysis_context(owner, "RETENTION")
    headers = auth_header(owner)
    created = client.post(
        "/api/deconfliction-analyses/",
        {
            "incident": str(incident.id),
            "approved_revision": str(revision.id),
        },
        content_type="application/json",
        **headers,
    )
    assert created.status_code == 201, created.content
    detail_url = f"/api/deconfliction-analyses/{created.json()['id']}/"

    assert client.put(detail_url, {}, content_type="application/json", **headers).status_code == 405
    assert (
        client.patch(detail_url, {}, content_type="application/json", **headers).status_code == 405
    )
    assert client.delete(detail_url, **headers).status_code == 405
    assert DeconflictionAnalysis.objects.filter(pk=created.json()["id"]).exists()

    legacy_input = {
        "schema_version": "rf-deconfliction-input-v1",
        "approved_revision": {"id": str(revision.id), "number": revision.number},
        "assignments": [{"channel_name": "SYN LEGACY", "tx_frequency_hz": 155_000_000}],
    }
    legacy_result = {
        "schema_version": "rf-deconfliction-result-v1",
        "input_sha256": canonical_digest(legacy_input),
        "warning_count": 1,
        "warnings": [
            {
                "rule_id": "RF-005",
                "severity": "caution",
                "explanation": "Synthetic retained legacy evidence.",
            }
        ],
        "disclaimer": DISCLAIMER,
    }
    legacy = DeconflictionAnalysis.objects.create(
        incident=incident,
        approved_revision=revision,
        rule_set_id="rf-deconfliction",
        rule_set_version="rf-deconfliction-v1-provisional",
        input_snapshot=legacy_input,
        input_sha256=canonical_digest(legacy_input),
        result_snapshot=legacy_result,
        result_sha256=canonical_digest(legacy_result),
        warning_count=1,
        created_by=owner,
    )

    retained = client.get(f"/api/deconfliction-analyses/{legacy.id}/", **headers)
    assert retained.status_code == 200
    assert retained.json()["rule_set_version"] == "rf-deconfliction-v1-provisional"
    assert retained.json()["input_snapshot"] == legacy_input
    assert retained.json()["result_snapshot"] == legacy_result
    assert retained.json()["result_snapshot"]["warnings"][0]["rule_id"] == "RF-005"


@pytest.mark.parametrize(
    ("snapshot_field", "expected_error"),
    [
        ("input_snapshot", "input digest is invalid"),
        ("result_snapshot", "result digest is invalid"),
    ],
)
@pytest.mark.django_db
@override_settings(ICT_APPROVED_DECONFLICTION_RULESETS=[RULE_SET_VERSION])
def test_analysis_approval_rejects_tampered_retained_snapshots(
    client,
    snapshot_field,
    expected_error,
):
    owner = user_with_role(f"deconfliction-tamper-{snapshot_field}", Role.COML)
    incident, revision = create_analysis_context(owner, f"TAMPER-{snapshot_field.upper()}")
    headers = auth_header(owner)
    created = client.post(
        "/api/deconfliction-analyses/",
        {
            "incident": str(incident.id),
            "approved_revision": str(revision.id),
        },
        content_type="application/json",
        **headers,
    )
    assert created.status_code == 201, created.content

    DeconflictionAnalysis.objects.filter(pk=created.json()["id"]).update(
        **{snapshot_field: {"tampered": True}}
    )
    rejected = client.post(
        f"/api/deconfliction-analyses/{created.json()['id']}/approve/",
        **headers,
    )
    assert rejected.status_code == 400
    assert expected_error in json.dumps(rejected.json()).lower()
    assert not AuditEvent.objects.filter(action="deconfliction_analysis.approved").exists()
    assert (
        DeconflictionAnalysis.objects.get(pk=created.json()["id"]).status
        == DeconflictionAnalysis.Status.DRAFT
    )
