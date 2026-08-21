import hashlib
import json

from django.db import transaction
from django.db.models.deletion import ProtectedError
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.policy import SITE_VIEW, user_has_permission
from apps.audit.services import record_event
from apps.plans.models import Assignment, PlanRevision
from apps.plans.serializers import AssignmentSerializer, PlanRevisionSerializer
from apps.sites.models import SiteAssignment

from .models import CollaborationChange

ASSIGNMENT_SNAPSHOT_FIELDS = (
    "id",
    "revision_id",
    "position",
    "function",
    "channel_name",
    "assignment",
    "conventional_channel_id",
    "trunked_talkgroup_id",
    "subscriber_profile_version_id",
    "resource_snapshot",
    "operating_classification",
    "technology_subtype",
    "rx_frequency_hz",
    "rx_channel_width_hz",
    "rx_squelch",
    "tx_frequency_hz",
    "tx_channel_width_hz",
    "tx_squelch",
    "mode",
    "remarks",
    "structured_note",
    "contact_name",
    "site_address",
    "phone_numbers",
    "contact_24_hour",
    "published_contact_fields",
    "contact_publication_purpose",
    "contact_publication_placement",
    "collaboration_version",
)
REVISION_EDIT_FIELDS = {
    "prepared_by_name",
    "prepared_by_position",
    "prepared_at",
}


def _canonical_digest(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def assignment_snapshot(assignment: Assignment) -> dict:
    snapshot = {
        field: str(value) if field.endswith("_id") and value is not None else value
        for field in ASSIGNMENT_SNAPSHOT_FIELDS
        if (value := getattr(assignment, field)) is not None
    }
    return json.loads(json.dumps(snapshot, default=str))


def revision_snapshot(revision: PlanRevision) -> dict:
    return {
        "id": str(revision.id),
        "status": revision.status,
        "prepared_by_name": revision.prepared_by_name,
        "prepared_by_position": revision.prepared_by_position,
        "prepared_at": revision.prepared_at.isoformat() if revision.prepared_at else None,
        "collaboration_version": revision.collaboration_version,
        "assignment_ids": [str(item) for item in revision.assignments.values_list("id", flat=True)],
    }


def _create_change(
    *,
    actor,
    revision,
    payload,
    payload_sha256,
    disposition,
    current_snapshot,
    resulting_version=None,
    result=None,
) -> CollaborationChange:
    change = CollaborationChange.objects.create(
        client_mutation_id=payload["client_mutation_id"],
        incident=revision.plan.incident,
        revision=revision,
        actor=actor,
        device_id=payload["device_id"],
        operation=payload["operation"],
        object_id=payload.get("object_id"),
        section=payload["section"],
        base_version=payload["base_version"],
        resulting_version=resulting_version,
        affected_fields=sorted(payload["changes"]),
        proposed_snapshot=payload["changes"],
        current_snapshot=current_snapshot,
        payload_sha256=payload_sha256,
        disposition=disposition,
        result=result or {},
    )
    record_event(
        actor=actor,
        action=f"collaboration.mutation_{disposition}",
        target=change,
        details={
            "revision_id": str(revision.id),
            "operation": payload["operation"],
            "section": payload["section"],
            "base_version": payload["base_version"],
            "resulting_version": resulting_version,
            "affected_fields": sorted(payload["changes"]),
            "payload_sha256": payload_sha256,
        },
    )
    return change


def _conflict(*, actor, revision, payload, digest, current_snapshot) -> CollaborationChange:
    intervening = CollaborationChange.objects.filter(
        revision=revision,
        disposition=CollaborationChange.Disposition.SAVED,
    )
    if payload.get("object_id"):
        intervening = intervening.filter(object_id=payload["object_id"])
    else:
        intervening = intervening.filter(
            operation__in={
                CollaborationChange.Operation.REVISION_UPDATE,
                CollaborationChange.Operation.ASSIGNMENT_CREATE,
                CollaborationChange.Operation.ASSIGNMENT_REORDER,
            }
        )
    intervening = intervening.select_related("actor").order_by("-created_at").first()
    result = {"detail": "The saved record changed after this editor loaded it."}
    if intervening:
        result.update(
            {
                "intervening_change_id": str(intervening.id),
                "intervening_actor_display_name": (
                    intervening.actor.get_full_name() or intervening.actor.get_username()
                ),
                "intervening_resulting_version": intervening.resulting_version,
            }
        )
    return _create_change(
        actor=actor,
        revision=revision,
        payload=payload,
        payload_sha256=digest,
        disposition=CollaborationChange.Disposition.CONFLICT,
        current_snapshot=current_snapshot,
        result=result,
    )


def _rejected(
    *,
    actor,
    revision,
    payload,
    digest,
    current_snapshot,
    detail,
    result=None,
):
    return _create_change(
        actor=actor,
        revision=revision,
        payload=payload,
        payload_sha256=digest,
        disposition=CollaborationChange.Disposition.REJECTED,
        current_snapshot=current_snapshot,
        result={**(result or {}), "detail": detail},
    )


@transaction.atomic
def apply_mutation(*, actor, request, payload: dict) -> CollaborationChange:
    """Apply one online mutation under row locks and retain every outcome."""

    digest = _canonical_digest(payload)
    existing = (
        CollaborationChange.objects.select_related("incident", "revision")
        .filter(client_mutation_id=payload["client_mutation_id"])
        .first()
    )
    if existing:
        if (
            existing.actor_id != actor.id
            or existing.device_id != payload["device_id"]
            or existing.payload_sha256 != digest
        ):
            raise ValidationError(
                {"client_mutation_id": "This identifier was already used for another mutation."}
            )
        return existing

    try:
        revision = (
            PlanRevision.objects.select_for_update()
            .select_related("plan__incident")
            .get(pk=payload["revision"])
        )
    except PlanRevision.DoesNotExist as exc:
        raise ValidationError({"revision": "Revision not found."}) from exc
    operation = payload["operation"]
    changes = payload["changes"]
    if revision.is_locked:
        return _rejected(
            actor=actor,
            revision=revision,
            payload=payload,
            digest=digest,
            current_snapshot=revision_snapshot(revision),
            detail="Approved revisions are immutable. Copy the revision to a new draft.",
        )

    if operation == CollaborationChange.Operation.REVISION_UPDATE:
        current = revision_snapshot(revision)
        unknown = sorted(set(changes) - REVISION_EDIT_FIELDS)
        if unknown:
            return _rejected(
                actor=actor,
                revision=revision,
                payload=payload,
                digest=digest,
                current_snapshot=current,
                detail=f"Unsupported revision fields: {', '.join(unknown)}.",
            )
        if revision.collaboration_version != payload["base_version"]:
            return _conflict(
                actor=actor,
                revision=revision,
                payload=payload,
                digest=digest,
                current_snapshot=current,
            )
        serializer = PlanRevisionSerializer(
            revision,
            data=changes,
            partial=True,
            context={"request": request},
        )
        if not serializer.is_valid():
            return _rejected(
                actor=actor,
                revision=revision,
                payload=payload,
                digest=digest,
                current_snapshot=current,
                detail=str(serializer.errors),
            )
        serializer.save(collaboration_version=revision.collaboration_version + 1)
        return _create_change(
            actor=actor,
            revision=revision,
            payload=payload,
            payload_sha256=digest,
            disposition=CollaborationChange.Disposition.SAVED,
            current_snapshot=current,
            resulting_version=revision.collaboration_version,
            result={"revision": str(revision.id), "version": revision.collaboration_version},
        )

    if operation == CollaborationChange.Operation.ASSIGNMENT_CREATE:
        current = revision_snapshot(revision)
        if revision.collaboration_version != payload["base_version"]:
            return _conflict(
                actor=actor,
                revision=revision,
                payload=payload,
                digest=digest,
                current_snapshot=current,
            )
        serializer = AssignmentSerializer(
            data={**changes, "revision": str(revision.id)},
            context={"request": request},
        )
        try:
            valid = serializer.is_valid()
        except PermissionDenied as exc:
            return _rejected(
                actor=actor,
                revision=revision,
                payload=payload,
                digest=digest,
                current_snapshot=current,
                detail=str(exc.detail),
            )
        if not valid:
            return _rejected(
                actor=actor,
                revision=revision,
                payload=payload,
                digest=digest,
                current_snapshot=current,
                detail=str(serializer.errors),
            )
        assignment = serializer.save()
        revision.collaboration_version += 1
        revision.save(update_fields=["collaboration_version", "updated_at"])
        return _create_change(
            actor=actor,
            revision=revision,
            payload=payload,
            payload_sha256=digest,
            disposition=CollaborationChange.Disposition.SAVED,
            current_snapshot=current,
            resulting_version=revision.collaboration_version,
            result={
                "assignment": str(assignment.id),
                "version": assignment.collaboration_version,
                "revision_version": revision.collaboration_version,
            },
        )

    if operation in {
        CollaborationChange.Operation.ASSIGNMENT_UPDATE,
        CollaborationChange.Operation.ASSIGNMENT_DELETE,
    }:
        try:
            assignment = (
                Assignment.objects.select_for_update()
                .select_related("revision__plan__incident")
                .get(pk=payload["object_id"], revision=revision)
            )
        except Assignment.DoesNotExist:
            return _rejected(
                actor=actor,
                revision=revision,
                payload=payload,
                digest=digest,
                current_snapshot={},
                detail="Assignment not found in this revision.",
            )
        current = assignment_snapshot(assignment)
        if assignment.collaboration_version != payload["base_version"]:
            return _conflict(
                actor=actor,
                revision=revision,
                payload=payload,
                digest=digest,
                current_snapshot=current,
            )
        if operation == CollaborationChange.Operation.ASSIGNMENT_DELETE:
            if changes:
                return _rejected(
                    actor=actor,
                    revision=revision,
                    payload=payload,
                    digest=digest,
                    current_snapshot=current,
                    detail="Delete does not accept changed fields.",
                )
            object_id = str(assignment.id)
            site_links = list(
                SiteAssignment.objects.select_for_update()
                .select_related("site")
                .filter(assignment=assignment)
                .order_by("id")
            )
            current["site_link_count"] = len(site_links)
            if site_links:
                plural = "link" if len(site_links) == 1 else "links"
                authorized_link_details = {}
                if user_has_permission(actor, SITE_VIEW, revision.plan.incident):
                    authorized_link_details = {
                        "linked_site_assignment_ids": [str(link.id) for link in site_links],
                        "linked_site_ids": [str(link.site_id) for link in site_links],
                    }
                return _rejected(
                    actor=actor,
                    revision=revision,
                    payload=payload,
                    digest=digest,
                    current_snapshot=current,
                    detail=(
                        f"This draft assignment has {len(site_links)} radio-site {plural}. "
                        "Review and remove the linked site associations in Radio site "
                        "planning before deleting the assignment."
                    ),
                    result={
                        "linked_site_count": len(site_links),
                        **authorized_link_details,
                    },
                )
            try:
                assignment.delete()
            except ProtectedError:
                return _rejected(
                    actor=actor,
                    revision=revision,
                    payload=payload,
                    digest=digest,
                    current_snapshot=current,
                    detail=(
                        "This draft assignment is linked to retained records that must be "
                        "removed before the assignment can be deleted."
                    ),
                )
            revision.collaboration_version += 1
            revision.save(update_fields=["collaboration_version", "updated_at"])
            change = _create_change(
                actor=actor,
                revision=revision,
                payload=payload,
                payload_sha256=digest,
                disposition=CollaborationChange.Disposition.SAVED,
                current_snapshot=current,
                resulting_version=revision.collaboration_version,
                result={
                    "deleted_assignment": object_id,
                    "revision_version": revision.collaboration_version,
                },
            )
            record_event(
                actor=actor,
                action="plan_assignment.deleted",
                target=revision,
                details={
                    "assignment_id": object_id,
                    "collaboration_change_id": str(change.id),
                },
            )
            return change
        serializer = AssignmentSerializer(
            assignment,
            data=changes,
            partial=True,
            context={"request": request},
        )
        try:
            valid = serializer.is_valid()
        except PermissionDenied as exc:
            return _rejected(
                actor=actor,
                revision=revision,
                payload=payload,
                digest=digest,
                current_snapshot=current,
                detail=str(exc.detail),
            )
        if not valid:
            return _rejected(
                actor=actor,
                revision=revision,
                payload=payload,
                digest=digest,
                current_snapshot=current,
                detail=str(serializer.errors),
            )
        serializer.save(collaboration_version=assignment.collaboration_version + 1)
        return _create_change(
            actor=actor,
            revision=revision,
            payload=payload,
            payload_sha256=digest,
            disposition=CollaborationChange.Disposition.SAVED,
            current_snapshot=current,
            resulting_version=assignment.collaboration_version,
            result={"assignment": str(assignment.id), "version": assignment.collaboration_version},
        )

    if operation == CollaborationChange.Operation.ASSIGNMENT_REORDER:
        current = revision_snapshot(revision)
        if revision.collaboration_version != payload["base_version"]:
            return _conflict(
                actor=actor,
                revision=revision,
                payload=payload,
                digest=digest,
                current_snapshot=current,
            )
        if set(changes) != {"assignment_ids"} or not isinstance(changes["assignment_ids"], list):
            return _rejected(
                actor=actor,
                revision=revision,
                payload=payload,
                digest=digest,
                current_snapshot=current,
                detail="Reorder requires only an assignment_ids array.",
            )
        assignments = list(revision.assignments.all())
        ordered_ids = list(map(str, changes["assignment_ids"]))
        if len(ordered_ids) != len(set(ordered_ids)) or set(ordered_ids) != {
            str(item.id) for item in assignments
        }:
            return _rejected(
                actor=actor,
                revision=revision,
                payload=payload,
                digest=digest,
                current_snapshot=current,
                detail="Provide every assignment exactly once.",
            )
        by_id = {str(item.id): item for item in assignments}
        for offset, item_id in enumerate(ordered_ids, 1):
            Assignment.objects.filter(pk=by_id[item_id].id).update(position=10000 + offset)
        for position, item_id in enumerate(ordered_ids, 1):
            Assignment.objects.filter(pk=by_id[item_id].id).update(position=position)
        revision.collaboration_version += 1
        revision.save(update_fields=["collaboration_version", "updated_at"])
        return _create_change(
            actor=actor,
            revision=revision,
            payload=payload,
            payload_sha256=digest,
            disposition=CollaborationChange.Disposition.SAVED,
            current_snapshot=current,
            resulting_version=revision.collaboration_version,
            result={
                "assignment_ids": ordered_ids,
                "revision_version": revision.collaboration_version,
            },
        )

    raise ValidationError({"operation": "Unsupported collaboration operation."})
