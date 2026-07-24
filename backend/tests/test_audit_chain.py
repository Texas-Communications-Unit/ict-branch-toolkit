import pytest
from django.contrib.auth import get_user_model
from django.db.models.query import QuerySet

from apps.accounts.models import Role, UserRoleAssignment
from apps.audit.models import GENESIS_HASH, AuditEvent
from apps.audit.services import _chained_record_hash, record_event, verify_audit_chain
from apps.incidents.models import Incident


def bypass_append_only_update(pk, **fields):
    """Simulate a database administrator editing a row directly, bypassing the app-layer
    append-only guard, to prove hash chaining (not just the guard) detects tampering."""
    QuerySet.update(AuditEvent.objects.filter(pk=pk), **fields)


def make_admin():
    admin = get_user_model().objects.create_superuser(
        "audit-admin", "audit-admin@example.invalid", "safe-test-password"
    )
    UserRoleAssignment.objects.create(user=admin, role=Role.ADMINISTRATOR)
    return admin


@pytest.mark.django_db
def test_first_event_chains_from_the_genesis_hash():
    admin = make_admin()
    incident = Incident.objects.create(
        name="Synthetic Chain Exercise", incident_number="SYN-CHAIN-1", created_by=admin
    )
    event = record_event(actor=admin, action="incident.created", target=incident)
    assert event.sequence == 0
    assert event.previous_hash == GENESIS_HASH
    assert event.record_hash == _chained_record_hash(
        previous_hash=GENESIS_HASH,
        sequence=0,
        actor=admin,
        action="incident.created",
        target_type=incident._meta.label_lower,
        target_id=str(incident.pk),
        details={},
    )


@pytest.mark.django_db
def test_successive_events_link_previous_hash_to_prior_record_hash():
    admin = make_admin()
    incident = Incident.objects.create(
        name="Synthetic Chain Exercise", incident_number="SYN-CHAIN-2", created_by=admin
    )
    first = record_event(actor=admin, action="incident.created", target=incident)
    second = record_event(actor=admin, action="incident.updated", target=incident, details={"n": 1})
    third = record_event(actor=admin, action="incident.updated", target=incident, details={"n": 2})

    assert second.sequence == first.sequence + 1
    assert third.sequence == second.sequence + 1
    assert second.previous_hash == first.record_hash
    assert third.previous_hash == second.record_hash
    assert len({first.record_hash, second.record_hash, third.record_hash}) == 3


@pytest.mark.django_db
def test_verify_audit_chain_passes_for_an_untouched_chain():
    admin = make_admin()
    incident = Incident.objects.create(
        name="Synthetic Chain Exercise", incident_number="SYN-CHAIN-3", created_by=admin
    )
    record_event(actor=admin, action="incident.created", target=incident)
    record_event(actor=admin, action="incident.updated", target=incident, details={"n": 1})

    ok, broken_at = verify_audit_chain()
    assert ok is True
    assert broken_at is None


@pytest.mark.django_db
def test_verify_audit_chain_detects_a_mutated_record():
    admin = make_admin()
    incident = Incident.objects.create(
        name="Synthetic Chain Exercise", incident_number="SYN-CHAIN-4", created_by=admin
    )
    record_event(actor=admin, action="incident.created", target=incident)
    tampered = record_event(
        actor=admin, action="incident.updated", target=incident, details={"n": 1}
    )
    record_event(actor=admin, action="incident.updated", target=incident, details={"n": 2})

    bypass_append_only_update(tampered.pk, details={"n": "tampered"})

    ok, broken_at = verify_audit_chain()
    assert ok is False
    assert broken_at.pk == tampered.pk


@pytest.mark.django_db
def test_verify_audit_chain_detects_a_severed_link():
    admin = make_admin()
    incident = Incident.objects.create(
        name="Synthetic Chain Exercise", incident_number="SYN-CHAIN-5", created_by=admin
    )
    record_event(actor=admin, action="incident.created", target=incident)
    second = record_event(actor=admin, action="incident.updated", target=incident, details={"n": 1})

    bypass_append_only_update(second.pk, previous_hash=GENESIS_HASH)

    ok, broken_at = verify_audit_chain()
    assert ok is False
    assert broken_at.pk == second.pk


@pytest.mark.django_db
def test_verify_audit_chain_passes_on_an_empty_log():
    ok, broken_at = verify_audit_chain()
    assert ok is True
    assert broken_at is None
