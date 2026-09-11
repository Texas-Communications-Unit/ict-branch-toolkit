from __future__ import annotations

import hashlib

from django.db import transaction
from django.db.models import Max
from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.accounts.models import Role
from apps.accounts.permissions import PolicyPermission
from apps.accounts.policy import PLAN_EDIT, PLAN_EXPORT, PLAN_VIEW, role_for_user, user_has_permission
from apps.audit.services import record_event

from .ics205b_export import render_ics205b_pdf, render_ics205b_xlsx
from .ics205b_models import ICS205BAssignment, ICS205BForm
from .ics205b_serializers import ICS205BAssignmentSerializer, ICS205BFormSerializer


def _scoped(queryset, user, incident_path="incident"):
    if role_for_user(user) == Role.ADMINISTRATOR:
        return queryset
    return queryset.filter(
        **{
            f"{incident_path}__memberships__user": user,
            f"{incident_path}__memberships__is_active": True,
        }
    ).distinct()


def _export_event(*, request, form: ICS205BForm, export_format: str, content: bytes):
    record_event(
        actor=request.user,
        action=f"ics205b.{export_format}_exported",
        target=form,
        details={
            "format": export_format,
            "content_sha256": hashlib.sha256(content).hexdigest(),
            "byte_size": len(content),
            "incident_id": str(form.incident_id),
            "operational_period_id": str(form.operational_period_id),
        },
    )


class ICS205BFormViewSet(viewsets.ModelViewSet):
    queryset = ICS205BForm.objects.none()
    serializer_class = ICS205BFormSerializer
    permission_classes = [PolicyPermission]
    policy_actions = {
        "list": PLAN_VIEW,
        "retrieve": PLAN_VIEW,
        "create": PLAN_EDIT,
        "update": PLAN_EDIT,
        "partial_update": PLAN_EDIT,
        "pdf": PLAN_EXPORT,
        "xlsx": PLAN_EXPORT,
    }

    def get_queryset(self):
        queryset = _scoped(
            ICS205BForm.objects.select_related("incident", "operational_period", "created_by")
            .prefetch_related("assignments"),
            self.request.user,
        )
        incident = self.request.query_params.get("incident")
        operational_period = self.request.query_params.get("operational_period")
        if incident:
            queryset = queryset.filter(incident_id=incident)
        if operational_period:
            queryset = queryset.filter(operational_period_id=operational_period)
        return queryset

    def perform_create(self, serializer):
        incident = serializer.validated_data["incident"]
        if not user_has_permission(self.request.user, PLAN_EDIT, incident):
            raise PermissionDenied("Your incident role cannot create ICS 205B forms.")
        form = serializer.save(created_by=self.request.user)
        record_event(actor=self.request.user, action="ics205b.created", target=form)

    def perform_update(self, serializer):
        incident = serializer.instance.incident
        if not user_has_permission(self.request.user, PLAN_EDIT, incident):
            raise PermissionDenied("Your incident role cannot edit ICS 205B forms.")
        form = serializer.save()
        record_event(
            actor=self.request.user,
            action="ics205b.updated",
            target=form,
            details={"changed_fields": sorted(serializer.validated_data)},
        )

    def destroy(self, request, *args, **kwargs):
        raise MethodNotAllowed("DELETE", detail="ICS 205B form history is retained.")

    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        form = self.get_object()
        if not user_has_permission(request.user, PLAN_EXPORT, form.incident):
            raise PermissionDenied("Your incident role cannot export ICS 205B forms.")
        content = render_ics205b_pdf(form)
        _export_event(request=request, form=form, export_format="pdf", content=content)
        response = HttpResponse(content, content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="ics-205b.pdf"'
        return response

    @action(detail=True, methods=["get"])
    def xlsx(self, request, pk=None):
        form = self.get_object()
        if not user_has_permission(request.user, PLAN_EXPORT, form.incident):
            raise PermissionDenied("Your incident role cannot export ICS 205B forms.")
        content = render_ics205b_xlsx(form)
        _export_event(request=request, form=form, export_format="xlsx", content=content)
        response = HttpResponse(
            content,
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )
        response["Content-Disposition"] = 'attachment; filename="ics-205b.xlsx"'
        return response


class ICS205BAssignmentViewSet(viewsets.ModelViewSet):
    queryset = ICS205BAssignment.objects.none()
    serializer_class = ICS205BAssignmentSerializer
    permission_classes = [PolicyPermission]
    policy_actions = {
        "list": PLAN_VIEW,
        "retrieve": PLAN_VIEW,
        "create": PLAN_EDIT,
        "update": PLAN_EDIT,
        "partial_update": PLAN_EDIT,
        "destroy": PLAN_EDIT,
        "reorder": PLAN_EDIT,
    }

    def get_queryset(self):
        queryset = _scoped(
            ICS205BAssignment.objects.select_related(
                "form__incident", "form__operational_period"
            ),
            self.request.user,
            "form__incident",
        )
        form_id = self.request.query_params.get("form")
        return queryset.filter(form_id=form_id) if form_id else queryset

    def perform_create(self, serializer):
        form = serializer.validated_data["form"]
        if not user_has_permission(self.request.user, PLAN_EDIT, form.incident):
            raise PermissionDenied("Your incident role cannot edit ICS 205B assignments.")
        if not serializer.validated_data.get("position"):
            serializer.validated_data["position"] = (
                form.assignments.aggregate(Max("position"))["position__max"] or 0
            ) + 1
        item = serializer.save()
        record_event(actor=self.request.user, action="ics205b.assignment_created", target=item)

    def perform_update(self, serializer):
        item = serializer.instance
        if not user_has_permission(self.request.user, PLAN_EDIT, item.form.incident):
            raise PermissionDenied("Your incident role cannot edit ICS 205B assignments.")
        item = serializer.save()
        record_event(
            actor=self.request.user,
            action="ics205b.assignment_updated",
            target=item,
            details={"changed_fields": sorted(serializer.validated_data)},
        )

    def perform_destroy(self, instance):
        if not user_has_permission(self.request.user, PLAN_EDIT, instance.form.incident):
            raise PermissionDenied("Your incident role cannot edit ICS 205B assignments.")
        form = instance.form
        deleted_id = str(instance.id)
        instance.delete()
        with transaction.atomic():
            for position, item in enumerate(form.assignments.all(), start=1):
                if item.position != position:
                    ICS205BAssignment.objects.filter(pk=item.pk).update(position=position)
        record_event(
            actor=self.request.user,
            action="ics205b.assignment_deleted",
            target=form,
            details={"assignment_id": deleted_id},
        )

    @action(detail=False, methods=["post"])
    def reorder(self, request):
        form_id = request.data.get("form")
        ordered_ids = request.data.get("assignment_ids", [])
        first_assignment = self.get_queryset().filter(form_id=form_id).first()
        if first_assignment is None:
            raise ValidationError({"form": "ICS 205B form not found or has no assignments."})
        form = first_assignment.form
        if not user_has_permission(request.user, PLAN_EDIT, form.incident):
            raise PermissionDenied("Your incident role cannot reorder ICS 205B assignments.")
        assignments = list(form.assignments.all())
        if set(map(str, ordered_ids)) != {str(item.id) for item in assignments}:
            raise ValidationError({"assignment_ids": "Provide every assignment exactly once."})
        by_id = {str(item.id): item for item in assignments}
        with transaction.atomic():
            for offset, item_id in enumerate(ordered_ids, 1):
                ICS205BAssignment.objects.filter(pk=by_id[str(item_id)].pk).update(
                    position=10000 + offset
                )
            for position, item_id in enumerate(ordered_ids, 1):
                ICS205BAssignment.objects.filter(pk=by_id[str(item_id)].pk).update(
                    position=position
                )
        record_event(actor=request.user, action="ics205b.assignments_reordered", target=form)
        return Response(self.get_serializer(form.assignments.all(), many=True).data)
