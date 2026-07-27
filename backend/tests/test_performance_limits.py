import json
import os
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, UserRoleAssignment
from apps.audit.models import AuditEvent
from apps.incidents.models import Incident, IncidentMembership, OperationalPeriod
from apps.plans.models import Assignment, AssignmentRelationship, ICS205Plan, PlanRevision
from apps.resources.models import ConventionalChannel, ResourceRelease, ResourceSource
from apps.sites.models import ManualRing, RadioSite

INCIDENT_TOTAL = 101
INCIDENT_PAGE_SIZE = 100
PERIODS_PER_INCIDENT = 2
INCIDENT_QUERY_BUDGET = 6
INCIDENT_RESPONSE_BUDGET = 128 * 1024
INCIDENT_UPDATE_QUERY_BUDGET = 12
INCIDENT_UPDATE_RESPONSE_BUDGET = 8 * 1024

RESOURCE_TOTAL = 1_001
RESOURCE_MAX_PAGE_SIZE = 1_000
RESOURCE_QUERY_BUDGET = 4
RESOURCE_RESPONSE_BUDGET = 1_536 * 1024

SITE_TOTAL = 101
SITE_PAGE_SIZE = 100
RINGS_PER_SITE = 3
SITE_QUERY_BUDGET = 5
SITE_RESPONSE_BUDGET = 256 * 1024

PLAN_TOTAL = 25
REVISIONS_PER_PLAN = 2
ASSIGNMENTS_PER_REVISION = 10
RELATIONSHIPS_PER_REVISION = 1
PLAN_QUERY_BUDGET = 8
PLAN_RESPONSE_BUDGET = 512 * 1024

pytestmark = pytest.mark.django_db


def authenticated_client(user) -> APIClient:
    if not user.is_superuser:
        # Query budgets deliberately isolate endpoint data access from role lookup.
        _ = user.toolkit_role
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def measured_get(client: APIClient, path: str):
    with CaptureQueriesContext(connection) as queries:
        response = client.get(path)
        content = response.content
    assert response.status_code == 200, content
    return response, len(queries), len(content)


def measured_patch(client: APIClient, path: str, payload: dict):
    with CaptureQueriesContext(connection) as queries:
        response = client.patch(path, payload, format="json")
        content = response.content
    assert response.status_code == 200, content
    return response, len(queries), len(content)


def assert_envelope(
    *,
    name: str,
    query_count: int,
    query_budget: int,
    response_bytes: int,
    response_budget: int,
) -> None:
    if os.getenv("ICT_PERFORMANCE_REPORT") == "1":
        print(
            json.dumps(
                {
                    "workload": name,
                    "database": connection.vendor,
                    "queries": query_count,
                    "query_budget": query_budget,
                    "response_bytes": response_bytes,
                    "response_budget": response_budget,
                },
                sort_keys=True,
            )
        )
    assert query_count <= query_budget
    assert response_bytes <= response_budget


def test_incident_list_envelope_for_scoped_reader():
    user = get_user_model().objects.create_user(
        "performance-reader", password="synthetic-test-password"
    )
    UserRoleAssignment.objects.create(user=user, role=Role.READ_ONLY, assigned_by=user)
    incidents = Incident.objects.bulk_create(
        [
            Incident(
                name=f"Synthetic Performance Incident {index:03d}",
                incident_number=f"SYN-PERF-{index:03d}",
                created_by=user,
            )
            for index in range(INCIDENT_TOTAL)
        ]
    )
    IncidentMembership.objects.bulk_create(
        [
            IncidentMembership(
                incident=incident,
                user=user,
                role=Role.READ_ONLY,
                assigned_by=user,
            )
            for incident in incidents
        ]
    )
    starts_at = timezone.now().replace(microsecond=0)
    OperationalPeriod.objects.bulk_create(
        [
            OperationalPeriod(
                incident=incident,
                name=f"Synthetic Operational Period {period_number}",
                starts_at=starts_at + timedelta(days=period_number),
                ends_at=starts_at + timedelta(days=period_number, hours=12),
                created_by=user,
            )
            for incident in incidents
            for period_number in range(1, PERIODS_PER_INCIDENT + 1)
        ]
    )

    response, query_count, response_bytes = measured_get(
        authenticated_client(user), "/api/incidents/"
    )
    payload = response.json()
    assert payload["count"] == INCIDENT_TOTAL
    assert len(payload["results"]) == INCIDENT_PAGE_SIZE
    assert payload["next"]
    assert all(
        len(incident["operational_periods"]) == PERIODS_PER_INCIDENT
        for incident in payload["results"]
    )
    assert all("incident.view" in incident["permissions"] for incident in payload["results"])
    assert_envelope(
        name="incident-list",
        query_count=query_count,
        query_budget=INCIDENT_QUERY_BUDGET,
        response_bytes=response_bytes,
        response_budget=INCIDENT_RESPONSE_BUDGET,
    )


def test_incident_update_envelope_includes_append_only_audit():
    user = get_user_model().objects.create_user(
        "performance-writer", password="synthetic-test-password"
    )
    UserRoleAssignment.objects.create(user=user, role=Role.COML, assigned_by=user)
    incident = Incident.objects.create(
        name="Synthetic Performance Write Exercise",
        incident_number="SYN-PERF-WRITE",
        created_by=user,
    )
    IncidentMembership.objects.create(
        incident=incident,
        user=user,
        role=Role.COML,
        assigned_by=user,
    )

    response, query_count, response_bytes = measured_patch(
        authenticated_client(user),
        f"/api/incidents/{incident.id}/",
        {"status": Incident.Status.ACTIVE},
    )

    assert response.json()["status"] == Incident.Status.ACTIVE
    event = AuditEvent.objects.get(action="incident.updated")
    assert event.details == {"changed_fields": ["status"]}
    assert_envelope(
        name="incident-update-with-audit",
        query_count=query_count,
        query_budget=INCIDENT_UPDATE_QUERY_BUDGET,
        response_bytes=response_bytes,
        response_budget=INCIDENT_UPDATE_RESPONSE_BUDGET,
    )


def test_resource_list_clamps_oversized_page_request():
    admin = get_user_model().objects.create_superuser(
        "performance-resource-admin", password="synthetic-test-password"
    )
    reader = get_user_model().objects.create_user(
        "performance-resource-reader", password="synthetic-test-password"
    )
    UserRoleAssignment.objects.create(user=reader, role=Role.READ_ONLY, assigned_by=admin)
    source = ResourceSource.objects.create(
        slug="synthetic-performance-library",
        name="Synthetic Performance Library",
        source_type=ResourceSource.Type.SYNTHETIC,
        authoritative_url="https://example.invalid/synthetic-performance-library",
    )
    release = ResourceRelease.objects.create(
        source=source,
        version="SYN-PERF-1",
        effective_status=ResourceRelease.Status.EFFECTIVE,
        content_sha256="0" * 64,
        document_title="Synthetic Performance Resource Library",
        publisher="Synthetic fixture",
        permitted_use="Synthetic testing only",
        transformation_method="Generated by deterministic automated tests",
        imported_by=admin,
    )
    ConventionalChannel.objects.bulk_create(
        [
            ConventionalChannel(
                release=release,
                identifier=f"SYN-PERF-{index:04d}",
                name=f"Synthetic Performance Channel {index:04d}",
                channel_use="Synthetic exercise",
                band="VHF",
                jurisdiction="Synthetic",
                rx_frequency_hz=150_000_000 + index * 1_000,
                tx_frequency_hz=150_000_000 + index * 1_000,
                bandwidth_hz=12_500,
                mode=ConventionalChannel.Mode.ANALOG_FM,
                eligibility="Synthetic test users",
                authorization="Not an authorization to transmit",
                restrictions="Synthetic data only",
                notes="Deterministic performance fixture",
            )
            for index in range(RESOURCE_TOTAL)
        ]
    )

    response, query_count, response_bytes = measured_get(
        authenticated_client(reader),
        "/api/conventional-channels/?page_size=100000",
    )
    payload = response.json()
    assert payload["count"] == RESOURCE_TOTAL
    assert len(payload["results"]) == RESOURCE_MAX_PAGE_SIZE
    assert payload["next"]
    assert_envelope(
        name="resource-list",
        query_count=query_count,
        query_budget=RESOURCE_QUERY_BUDGET,
        response_bytes=response_bytes,
        response_budget=RESOURCE_RESPONSE_BUDGET,
    )


def test_radio_site_list_envelope_with_nested_rings():
    admin = get_user_model().objects.create_superuser(
        "performance-site-admin", password="synthetic-test-password"
    )
    reader = get_user_model().objects.create_user(
        "performance-site-reader", password="synthetic-test-password"
    )
    UserRoleAssignment.objects.create(user=reader, role=Role.READ_ONLY, assigned_by=admin)
    incident = Incident.objects.create(
        name="Synthetic Performance Mapping Exercise",
        incident_number="SYN-PERF-MAP",
        created_by=admin,
    )
    IncidentMembership.objects.create(
        incident=incident,
        user=reader,
        role=Role.READ_ONLY,
        assigned_by=admin,
    )
    sites = [
        RadioSite.objects.create(
            incident=incident,
            name=f"Synthetic Performance Site {index:03d}",
            description="Synthetic site used only for deterministic performance testing",
            latitude=f"{33 + index / 10_000:.6f}",
            longitude=f"{-97 - index / 10_000:.6f}",
            entered_coordinate="Synthetic decimal-degree fixture",
            created_by=admin,
        )
        for index in range(SITE_TOTAL)
    ]
    ManualRing.objects.bulk_create(
        [
            ManualRing(
                site=site,
                ring_type=ring_type,
                radius_m=(ring_number + 1) * 5_000,
                label=f"Synthetic {ring_type} ring",
            )
            for site in sites
            for ring_number, ring_type in enumerate(
                (
                    ManualRing.Type.OPERATIONAL,
                    ManualRing.Type.FRINGE,
                    ManualRing.Type.COORDINATION,
                )
            )
        ]
    )

    response, query_count, response_bytes = measured_get(
        authenticated_client(reader), f"/api/radio-sites/?incident={incident.id}"
    )
    payload = response.json()
    assert payload["count"] == SITE_TOTAL
    assert len(payload["results"]) == SITE_PAGE_SIZE
    assert payload["next"]
    assert all(len(site["rings"]) == RINGS_PER_SITE for site in payload["results"])
    assert_envelope(
        name="radio-site-list",
        query_count=query_count,
        query_budget=SITE_QUERY_BUDGET,
        response_bytes=response_bytes,
        response_budget=SITE_RESPONSE_BUDGET,
    )


def test_plan_list_envelope_with_nested_revisions_and_assignments():
    admin = get_user_model().objects.create_superuser(
        "performance-plan-admin", password="synthetic-test-password"
    )
    reader = get_user_model().objects.create_user(
        "performance-plan-reader", password="synthetic-test-password"
    )
    UserRoleAssignment.objects.create(user=reader, role=Role.READ_ONLY, assigned_by=admin)
    incident = Incident.objects.create(
        name="Synthetic Performance Planning Exercise",
        incident_number="SYN-PERF-PLAN",
        created_by=admin,
    )
    IncidentMembership.objects.create(
        incident=incident,
        user=reader,
        role=Role.READ_ONLY,
        assigned_by=admin,
    )
    starts_at = timezone.now().replace(microsecond=0)
    periods = OperationalPeriod.objects.bulk_create(
        [
            OperationalPeriod(
                incident=incident,
                name=f"Synthetic Operational Period {index:02d}",
                starts_at=starts_at + timedelta(days=index),
                ends_at=starts_at + timedelta(days=index, hours=12),
                created_by=admin,
            )
            for index in range(PLAN_TOTAL)
        ]
    )
    plans = ICS205Plan.objects.bulk_create(
        [
            ICS205Plan(
                incident=incident,
                operational_period=period,
                title=f"Synthetic Performance ICS-205 {index:02d}",
                created_by=admin,
            )
            for index, period in enumerate(periods)
        ]
    )
    revisions = PlanRevision.objects.bulk_create(
        [
            PlanRevision(
                plan=plan,
                number=revision_number,
                status=(
                    PlanRevision.Status.APPROVED
                    if revision_number == 1
                    else PlanRevision.Status.DRAFT
                ),
                created_by=admin,
                approved_by=admin if revision_number == 1 else None,
                approved_at=starts_at if revision_number == 1 else None,
            )
            for plan in plans
            for revision_number in range(1, REVISIONS_PER_PLAN + 1)
        ]
    )
    assignments = Assignment.objects.bulk_create(
        [
            Assignment(
                revision=revision,
                position=position,
                function="Synthetic tactical assignment",
                channel_name=f"SYN PERF {position:02d}",
                assignment="Synthetic exercise operations",
                resource_snapshot={"type": "synthetic", "identifier": f"SYN-{position:02d}"},
                rx_frequency_hz=150_000_000 + position * 1_000,
                tx_frequency_hz=150_000_000 + position * 1_000,
                mode="Analog FM",
                remarks="Synthetic data only",
            )
            for revision in revisions
            for position in range(1, ASSIGNMENTS_PER_REVISION + 1)
        ]
    )
    assignments_by_revision = {
        revision.id: [
            assignment for assignment in assignments if assignment.revision_id == revision.id
        ]
        for revision in revisions
    }
    relationships = AssignmentRelationship.objects.bulk_create(
        [
            AssignmentRelationship(
                revision=revision,
                relationship_type=AssignmentRelationship.Type.PATCH,
                label="Synthetic performance patch",
            )
            for revision in revisions
        ]
    )
    for relationship in relationships:
        relationship.assignments.add(*assignments_by_revision[relationship.revision_id][:2])

    response, query_count, response_bytes = measured_get(
        authenticated_client(reader), "/api/ics205-plans/"
    )
    payload = response.json()
    assert payload["count"] == PLAN_TOTAL
    assert len(payload["results"]) == PLAN_TOTAL
    assert sum(len(plan["revisions"]) for plan in payload["results"]) == (
        PLAN_TOTAL * REVISIONS_PER_PLAN
    )
    assert (
        sum(
            len(revision["assignments"])
            for plan in payload["results"]
            for revision in plan["revisions"]
        )
        == PLAN_TOTAL * REVISIONS_PER_PLAN * ASSIGNMENTS_PER_REVISION
    )
    assert (
        sum(
            len(revision["relationships"])
            for plan in payload["results"]
            for revision in plan["revisions"]
        )
        == PLAN_TOTAL * REVISIONS_PER_PLAN * RELATIONSHIPS_PER_REVISION
    )
    assert_envelope(
        name="plan-list",
        query_count=query_count,
        query_budget=PLAN_QUERY_BUDGET,
        response_bytes=response_bytes,
        response_budget=PLAN_RESPONSE_BUDGET,
    )
