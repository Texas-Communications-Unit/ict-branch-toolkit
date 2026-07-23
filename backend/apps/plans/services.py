from copy import deepcopy

from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.services import record_event

from .models import AssignmentRelationship, PlanRevision


def ensure_draft(revision):
    if revision.is_locked:
        raise ValidationError("Approved revisions are immutable. Copy the revision to a new draft.")


def resource_snapshot(data):
    channel = data.get("conventional_channel")
    talkgroup = data.get("trunked_talkgroup")
    if channel:
        release = channel.release
        return {
            "type": "conventional",
            "resource_id": str(channel.id),
            "identifier": channel.identifier,
            "name": channel.name,
            "source": release.source.slug,
            "source_type": release.source.source_type,
            "release": release.version,
            "content_sha256": release.content_sha256,
        }
    if talkgroup:
        release = talkgroup.release
        return {
            "type": "talkgroup",
            "resource_id": str(talkgroup.id),
            "identifier": talkgroup.identifier,
            "name": talkgroup.name,
            "source": release.source.slug,
            "source_type": release.source.source_type,
            "release": release.version,
            "content_sha256": release.content_sha256,
        }
    return {"type": "incident", "name": data.get("channel_name", "")}


@transaction.atomic
def copy_revision(revision, actor):
    next_number = (revision.plan.revisions.aggregate(Max("number"))["number__max"] or 0) + 1
    copied = PlanRevision.objects.create(
        plan=revision.plan,
        number=next_number,
        copied_from=revision,
        created_by=actor,
        prepared_by_name=revision.prepared_by_name,
        prepared_by_position=revision.prepared_by_position,
        prepared_at=revision.prepared_at,
    )
    assignment_map = {}
    for assignment in revision.assignments.all():
        old_id = assignment.id
        assignment.pk = None
        assignment.id = None
        assignment.revision = copied
        assignment.resource_snapshot = deepcopy(assignment.resource_snapshot)
        assignment.save()
        assignment_map[old_id] = assignment
    for relationship in revision.relationships.prefetch_related("assignments"):
        members = list(relationship.assignments.all())
        new_relationship = AssignmentRelationship.objects.create(
            revision=copied,
            relationship_type=relationship.relationship_type,
            label=relationship.label,
        )
        new_relationship.assignments.set(assignment_map[item.id] for item in members)
    from apps.sites.services import copy_revision_sites

    copy_revision_sites(revision, assignment_map)
    record_event(
        actor=actor,
        action="plan_revision.copied",
        target=copied,
        details={"source_revision_id": str(revision.id)},
    )
    return copied


@transaction.atomic
def approve_revision(revision, actor):
    ensure_draft(revision)
    if not revision.assignments.exists():
        raise ValidationError("A revision must contain at least one assignment before approval.")
    for relationship in revision.relationships.prefetch_related("assignments"):
        members = list(relationship.assignments.all())
        if any(item.revision_id != revision.id for item in members):
            raise ValidationError("Relationship assignments must belong to this revision.")
        if relationship.relationship_type == AssignmentRelationship.Type.PATCH and len(members) < 2:
            raise ValidationError("A Patch relationship requires at least two assignments.")
    from apps.sites.services import freeze_revision_sites

    freeze_revision_sites(revision)
    revision.status = PlanRevision.Status.APPROVED
    revision.approved_by = actor
    revision.approved_at = timezone.now()
    revision.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    record_event(actor=actor, action="plan_revision.approved", target=revision)
    return revision
