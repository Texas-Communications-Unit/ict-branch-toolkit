from django.db import transaction
from django.db.models import Max
from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.accounts.models import Role
from apps.accounts.permissions import PolicyPermission
from apps.accounts.policy import (
    PLAN_APPROVE,
    PLAN_EDIT,
    PLAN_EXPORT,
    PLAN_VIEW,
    role_for_user,
    user_has_permission,
)
from apps.audit.services import record_event, record_export

from .models import Assignment, AssignmentRelationship, ICS205Plan, PlanRevision
from .pdf import render_ics205
from .serializers import (
    AssignmentSerializer,
    PlanRevisionSerializer,
    PlanSerializer,
    RelationshipSerializer,
)
from .services import approve_revision, copy_revision, ensure_draft


def scoped(queryset, user, path="plan__incident"):
    if role_for_user(user) == Role.ADMINISTRATOR:
        return queryset
    return queryset.filter(
        **{
            f"{path}__memberships__user": user,
            f"{path}__memberships__is_active": True,
        }
    ).distinct()


class PlanViewSet(viewsets.ModelViewSet):
    queryset = ICS205Plan.objects.none()
    serializer_class = PlanSerializer
    permission_classes = [PolicyPermission]
    policy_actions = {
        "list": PLAN_VIEW,
        "retrieve": PLAN_VIEW,
        "create": PLAN_EDIT,
        "update": PLAN_EDIT,
        "partial_update": PLAN_EDIT,
    }

    def get_queryset(self):
        return scoped(
            ICS205Plan.objects.filter(archived_at__isnull=True)
            .select_related("incident", "operational_period")
            .prefetch_related("revisions__assignments", "revisions__relationships"),
            self.request.user,
            "incident",
        )

    def perform_create(self, serializer):
        incident = serializer.validated_data["incident"]
        if not user_has_permission(self.request.user, PLAN_EDIT, incident):
            raise PermissionDenied("Your incident role cannot create plans.")
        plan = serializer.save(created_by=self.request.user)
        revision = PlanRevision.objects.create(plan=plan, number=1, created_by=self.request.user)
        record_event(actor=self.request.user, action="plan.created", target=plan)
        record_event(actor=self.request.user, action="plan_revision.created", target=revision)

    def perform_update(self, serializer):
        plan = serializer.save()
        record_event(
            actor=self.request.user,
            action="plan.updated",
            target=plan,
            details={"changed_fields": sorted(serializer.validated_data)},
        )

    def destroy(self, request, *args, **kwargs):
        raise MethodNotAllowed("DELETE", detail="Plans retain their revision and audit history.")


class RevisionViewSet(viewsets.ModelViewSet):
    queryset = PlanRevision.objects.none()
    serializer_class = PlanRevisionSerializer
    permission_classes = [PolicyPermission]
    policy_actions = {
        "list": PLAN_VIEW,
        "retrieve": PLAN_VIEW,
        "create": PLAN_EDIT,
        "update": PLAN_EDIT,
        "partial_update": PLAN_EDIT,
        "copy": PLAN_EDIT,
        "approve": PLAN_APPROVE,
        "compare": PLAN_VIEW,
        "pdf": PLAN_EXPORT,
    }

    def get_queryset(self):
        return scoped(
            PlanRevision.objects.select_related(
                "plan__incident", "plan__operational_period", "created_by", "approved_by"
            ).prefetch_related("assignments", "relationships__assignments"),
            self.request.user,
        )

    def perform_create(self, serializer):
        plan = serializer.validated_data["plan"]
        if not user_has_permission(self.request.user, PLAN_EDIT, plan.incident):
            raise PermissionDenied("Your incident role cannot create revisions.")
        if plan.revisions.filter(status=PlanRevision.Status.DRAFT).exists():
            raise ValidationError("This plan already has an editable draft.")
        number = (plan.revisions.aggregate(Max("number"))["number__max"] or 0) + 1
        revision = serializer.save(number=number, created_by=self.request.user)
        record_event(actor=self.request.user, action="plan_revision.created", target=revision)

    def perform_update(self, serializer):
        ensure_draft(serializer.instance)
        revision = serializer.save()
        record_event(
            actor=self.request.user,
            action="plan_revision.updated",
            target=revision,
            details={"changed_fields": sorted(serializer.validated_data)},
        )

    def destroy(self, request, *args, **kwargs):
        raise MethodNotAllowed("DELETE", detail="Plan revisions are retained.")

    @action(detail=True, methods=["post"])
    def copy(self, request, pk=None):
        source = self.get_object()
        if source.plan.revisions.filter(status=PlanRevision.Status.DRAFT).exists():
            raise ValidationError("This plan already has an editable draft.")
        return Response(self.get_serializer(copy_revision(source, request.user)).data, status=201)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        revision = self.get_object()
        if not user_has_permission(request.user, PLAN_APPROVE, revision.plan.incident):
            raise PermissionDenied("Your incident role cannot approve plans.")
        return Response(self.get_serializer(approve_revision(revision, request.user)).data)

    @action(detail=True, methods=["get"])
    def compare(self, request, pk=None):
        revision = self.get_object()
        other_id = request.query_params.get("other")
        try:
            other = revision.plan.revisions.get(pk=other_id)
        except PlanRevision.DoesNotExist as exc:
            raise ValidationError({"other": "Select another revision from this plan."}) from exc
        left = {str(item.id): item for item in revision.assignments.all()}
        right = {str(item.id): item for item in other.assignments.all()}
        if other.copied_from_id == revision.id:
            right = {str(item.position): item for item in other.assignments.all()}
            left = {str(item.position): item for item in revision.assignments.all()}
        fields = [
            "function",
            "channel_name",
            "assignment",
            "rx_frequency_hz",
            "tx_frequency_hz",
            "mode",
            "remarks",
        ]
        changes = []
        for key in sorted(set(left) | set(right)):
            before, after = left.get(key), right.get(key)
            changed = [
                field
                for field in fields
                if getattr(before, field, None) != getattr(after, field, None)
            ]
            if changed or before is None or after is None:
                changes.append(
                    {
                        "key": key,
                        "before": str(before.id) if before else None,
                        "after": str(after.id) if after else None,
                        "changed_fields": changed,
                    }
                )
        return Response(
            {"revision": revision.number, "other_revision": other.number, "changes": changes}
        )

    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        revision = self.get_object()
        if not user_has_permission(request.user, PLAN_EXPORT, revision.plan.incident):
            raise PermissionDenied("Your incident role cannot export official plans.")
        try:
            content = render_ics205(revision)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        record_export(
            actor=request.user,
            action="plan_revision.pdf_exported",
            revision=revision,
            export_format="pdf",
            content=content,
        )
        response = HttpResponse(content, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="ics-205-revision-{revision.number}.pdf"'
        )
        return response


class AssignmentViewSet(viewsets.ModelViewSet):
    queryset = Assignment.objects.none()
    serializer_class = AssignmentSerializer
    permission_classes = [PolicyPermission]
    policy_actions = {
        "list": PLAN_VIEW,
        "retrieve": PLAN_VIEW,
        "create": PLAN_EDIT,
        "update": PLAN_EDIT,
        "partial_update": PLAN_EDIT,
        "destroy": PLAN_EDIT,
    }

    def get_queryset(self):
        return scoped(
            Assignment.objects.select_related(
                "revision__plan__incident",
                "conventional_channel__release__source",
                "trunked_talkgroup__release__source",
            ),
            self.request.user,
            "revision__plan__incident",
        )

    def perform_create(self, serializer):
        revision = serializer.validated_data["revision"]
        if not user_has_permission(self.request.user, PLAN_EDIT, revision.plan.incident):
            raise PermissionDenied("Your incident role cannot edit plan assignments.")
        assignment = serializer.save()
        record_event(actor=self.request.user, action="plan_assignment.created", target=assignment)

    def perform_update(self, serializer):
        assignment = serializer.save()
        record_event(actor=self.request.user, action="plan_assignment.updated", target=assignment)

    def perform_destroy(self, instance):
        ensure_draft(instance.revision)
        target_id = str(instance.id)
        revision = instance.revision
        instance.delete()
        record_event(
            actor=self.request.user,
            action="plan_assignment.deleted",
            target=revision,
            details={"assignment_id": target_id},
        )

    @action(detail=False, methods=["post"])
    def reorder(self, request):
        revision_id = request.data.get("revision")
        ordered_ids = request.data.get("assignment_ids", [])
        try:
            revision = PlanRevision.objects.get(pk=revision_id)
        except PlanRevision.DoesNotExist as exc:
            raise ValidationError({"revision": "Revision not found."}) from exc
        ensure_draft(revision)
        if not user_has_permission(request.user, PLAN_EDIT, revision.plan.incident):
            raise PermissionDenied("Your incident role cannot reorder assignments.")
        assignments = list(revision.assignments.all())
        if set(map(str, ordered_ids)) != {str(item.id) for item in assignments}:
            raise ValidationError({"assignment_ids": "Provide every assignment exactly once."})
        by_id = {str(item.id): item for item in assignments}
        with transaction.atomic():
            for offset, item_id in enumerate(ordered_ids, 1):
                Assignment.objects.filter(pk=by_id[str(item_id)].id).update(position=10000 + offset)
            for position, item_id in enumerate(ordered_ids, 1):
                Assignment.objects.filter(pk=by_id[str(item_id)].id).update(position=position)
        record_event(actor=request.user, action="plan_assignments.reordered", target=revision)
        return Response(self.get_serializer(revision.assignments.all(), many=True).data)


class RelationshipViewSet(viewsets.ModelViewSet):
    queryset = AssignmentRelationship.objects.none()
    serializer_class = RelationshipSerializer
    permission_classes = [PolicyPermission]
    policy_actions = {
        "list": PLAN_VIEW,
        "retrieve": PLAN_VIEW,
        "create": PLAN_EDIT,
        "update": PLAN_EDIT,
        "partial_update": PLAN_EDIT,
        "destroy": PLAN_EDIT,
    }

    def get_queryset(self):
        return scoped(
            AssignmentRelationship.objects.select_related(
                "revision__plan__incident"
            ).prefetch_related("assignments"),
            self.request.user,
            "revision__plan__incident",
        )

    def perform_create(self, serializer):
        revision = serializer.validated_data["revision"]
        if not user_has_permission(self.request.user, PLAN_EDIT, revision.plan.incident):
            raise PermissionDenied("Your incident role cannot create plan relationships.")
        relationship = serializer.save()
        record_event(
            actor=self.request.user, action="plan_relationship.created", target=relationship
        )

    def perform_update(self, serializer):
        relationship = serializer.save()
        record_event(
            actor=self.request.user,
            action="plan_relationship.updated",
            target=relationship,
            details={"changed_fields": sorted(serializer.validated_data)},
        )

    def perform_destroy(self, instance):
        ensure_draft(instance.revision)
        relationship_id = str(instance.id)
        revision = instance.revision
        instance.delete()
        record_event(
            actor=self.request.user,
            action="plan_relationship.deleted",
            target=revision,
            details={"relationship_id": relationship_id},
        )
