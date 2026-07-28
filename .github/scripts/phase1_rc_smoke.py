"""Synthetic installed-stack smoke checks for the Phase 1 release candidate.

Run this through ``manage.py shell`` inside the production backend container.
The script deliberately creates only synthetic evaluation records and prints a
sanitized result summary suitable for release evidence.
"""

from django.contrib.auth import get_user_model
from django.test import Client
from rest_framework.authtoken.models import Token

from apps.accounts.models import Role, UserRoleAssignment
from apps.audit.models import AuditEvent
from apps.audit.services import verify_audit_chain
from apps.incidents.models import Incident, IncidentMembership, OperationalPeriod
from apps.plans.models import Assignment, ICS205Plan, PlanRevision


PASSWORD = "synthetic-evaluation-password"
User = get_user_model()


def create_user(username: str, role: str):
    user = User.objects.create_user(
        username=username,
        email=f"{username}@example.invalid",
        password=PASSWORD,
    )
    UserRoleAssignment.objects.create(user=user, role=role)
    return user


owner = create_user("rc-synthetic-owner", Role.COML)
evaluator = create_user("rc-synthetic-evaluator", Role.READ_ONLY)

assigned_incident = Incident.objects.create(
    name="Synthetic RC Assigned Incident",
    incident_number="SYN-RC-001",
    created_by=owner,
)
hidden_incident = Incident.objects.create(
    name="Synthetic RC Hidden Incident",
    incident_number="SYN-RC-002",
    created_by=owner,
)
IncidentMembership.objects.create(
    incident=assigned_incident,
    user=evaluator,
    role=Role.COMT,
    assigned_by=owner,
)
IncidentMembership.objects.create(
    incident=assigned_incident,
    user=owner,
    role=Role.COML,
    assigned_by=owner,
)
assigned_period = OperationalPeriod.objects.create(
    incident=assigned_incident,
    name="Synthetic RC Operational Period",
    starts_at="2026-07-28T08:00:00Z",
    ends_at="2026-07-28T20:00:00Z",
    created_by=owner,
)
OperationalPeriod.objects.create(
    incident=hidden_incident,
    name="Synthetic Hidden Operational Period",
    starts_at="2026-07-28T08:00:00Z",
    ends_at="2026-07-28T20:00:00Z",
    created_by=owner,
)

client = Client(HTTP_HOST="localhost")
evaluator_token = Token.objects.create(user=evaluator)
evaluator_auth = {"HTTP_AUTHORIZATION": f"Token {evaluator_token.key}"}

incident_list = client.get("/api/incidents/", **evaluator_auth)
assert incident_list.status_code == 200, incident_list.content
incident_ids = [row["id"] for row in incident_list.json()["results"]]
assert incident_ids == [str(assigned_incident.id)], incident_ids

hidden_detail = client.get(f"/api/incidents/{hidden_incident.id}/", **evaluator_auth)
assert hidden_detail.status_code == 404, hidden_detail.content

plan = ICS205Plan.objects.create(
    incident=assigned_incident,
    operational_period=assigned_period,
    created_by=owner,
)
revision = PlanRevision.objects.create(
    plan=plan,
    number=1,
    prepared_by_name="Synthetic RC Planner",
    prepared_by_position="COML",
    created_by=owner,
)
Assignment.objects.create(
    revision=revision,
    position=1,
    function="Command",
    channel_name="SYN RC CALL",
    assignment="Synthetic release-candidate evaluation",
    resource_snapshot={"type": "incident", "name": "SYN RC CALL"},
    rx_frequency_hz=155_001_000,
    tx_frequency_hz=155_001_000,
    rx_squelch="CSQ",
    tx_squelch="CSQ",
    mode="Analog FM",
    remarks="Synthetic evaluation only",
)

owner_token = Token.objects.create(user=owner)
owner_auth = {"HTTP_AUTHORIZATION": f"Token {owner_token.key}"}
approved = client.post(f"/api/plan-revisions/{revision.id}/approve/", **owner_auth)
assert approved.status_code == 200, approved.content
exported = client.get(f"/api/plan-revisions/{revision.id}/pdf/", **owner_auth)
assert exported.status_code == 200, exported.content
assert exported["Content-Type"] == "application/pdf"
assert exported.content.startswith(b"%PDF")

export_event = AuditEvent.objects.get(action="plan_revision.pdf_exported")
assert export_event.details["content_sha256"]
assert export_event.details["byte_size"] == len(exported.content)

chain_ok, broken_event = verify_audit_chain()
assert chain_ok and broken_event is None

print(
    {
        "synthetic_records_only": True,
        "incident_scope_enforced": True,
        "approved_export_verified": True,
        "audit_chain_ok": True,
        "audit_event_count": AuditEvent.objects.count(),
    }
)
