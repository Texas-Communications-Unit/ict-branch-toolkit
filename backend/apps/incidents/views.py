from django.db import connection
from django.db.models import Prefetch
from django.http import JsonResponse
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.accounts.models import Role
from apps.accounts.policy import (
    INCIDENT_ARCHIVE,
    INCIDENT_CHANGE,
    INCIDENT_CREATE,
    INCIDENT_VIEW,
    MEMBERSHIP_MANAGE,
    PERIOD_ARCHIVE,
    PERIOD_CHANGE,
    PERIOD_CREATE,
    role_for_user,
    user_has_permission,
)
from apps.audit.services import record_event

from .models import Incident, IncidentMembership, OperationalPeriod
from .permissions import PolicyPermission
from .serializers import (
    IncidentMembershipSerializer,
    IncidentSerializer,
    OperationalPeriodSerializer,
)


def health(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()

    payload = {"status": "ok", "database": connection.vendor}
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute("SELECT PostGIS_Version()")
            payload["postgis"] = cursor.fetchone()[0]
    return JsonResponse(payload)


class IncidentViewSet(viewsets.ModelViewSet):
    queryset = Incident.objects.all()
    serializer_class = IncidentSerializer
    permission_classes = [PolicyPermission]
    policy_actions = {
        "list": INCIDENT_VIEW,
        "retrieve": INCIDENT_VIEW,
        "create": INCIDENT_CREATE,
        "update": INCIDENT_CHANGE,
        "partial_update": INCIDENT_CHANGE,
        "archive": INCIDENT_ARCHIVE,
    }

    def get_queryset(self):
        queryset = Incident.objects.filter(archived_at__isnull=True).prefetch_related(
            Prefetch(
                "operational_periods",
                queryset=OperationalPeriod.objects.filter(archived_at__isnull=True),
            ),
            "memberships",
        )
        if role_for_user(self.request.user) == Role.ADMINISTRATOR:
            return queryset
        return queryset.filter(
            memberships__user=self.request.user, memberships__is_active=True
        ).distinct()

    def perform_create(self, serializer):
        incident = serializer.save(created_by=self.request.user)
        IncidentMembership.objects.create(
            incident=incident,
            user=self.request.user,
            role=role_for_user(self.request.user),
            assigned_by=self.request.user,
        )
        record_event(actor=self.request.user, action="incident.created", target=incident)

    def perform_update(self, serializer):
        if serializer.instance.archived_at:
            raise ValidationError("Archived incidents cannot be changed.")
        incident = serializer.save()
        record_event(
            actor=self.request.user,
            action="incident.updated",
            target=incident,
            details={"changed_fields": sorted(serializer.validated_data)},
        )

    def destroy(self, request, *args, **kwargs):
        raise MethodNotAllowed("DELETE", detail="Archive incidents instead of deleting them.")

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        incident = self.get_object()
        incident.archived_at = timezone.now()
        incident.save(update_fields=["archived_at", "updated_at"])
        record_event(actor=request.user, action="incident.archived", target=incident)
        return Response(self.get_serializer(incident).data)


class OperationalPeriodViewSet(viewsets.ModelViewSet):
    queryset = OperationalPeriod.objects.all()
    serializer_class = OperationalPeriodSerializer
    permission_classes = [PolicyPermission]
    policy_actions = {
        "list": INCIDENT_VIEW,
        "retrieve": INCIDENT_VIEW,
        "create": PERIOD_CREATE,
        "update": PERIOD_CHANGE,
        "partial_update": PERIOD_CHANGE,
        "archive": PERIOD_ARCHIVE,
    }

    def get_queryset(self):
        queryset = OperationalPeriod.objects.filter(
            archived_at__isnull=True, incident__archived_at__isnull=True
        ).select_related("incident")
        if role_for_user(self.request.user) == Role.ADMINISTRATOR:
            return queryset
        return queryset.filter(
            incident__memberships__user=self.request.user,
            incident__memberships__is_active=True,
        ).distinct()

    def perform_create(self, serializer):
        incident = serializer.validated_data["incident"]
        if incident.archived_at:
            raise ValidationError("Operational periods cannot be added to an archived incident.")
        if not user_has_permission(self.request.user, PERIOD_CREATE, incident):
            raise PermissionDenied("Your incident role cannot add operational periods.")
        period = serializer.save(created_by=self.request.user)
        record_event(actor=self.request.user, action="operational_period.created", target=period)

    def perform_update(self, serializer):
        if serializer.instance.archived_at:
            raise ValidationError("Archived operational periods cannot be changed.")
        period = serializer.save()
        record_event(
            actor=self.request.user,
            action="operational_period.updated",
            target=period,
            details={"changed_fields": sorted(serializer.validated_data)},
        )

    def destroy(self, request, *args, **kwargs):
        raise MethodNotAllowed(
            "DELETE", detail="Archive operational periods instead of deleting them."
        )

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        period = self.get_object()
        period.archived_at = timezone.now()
        period.save(update_fields=["archived_at", "updated_at"])
        record_event(actor=request.user, action="operational_period.archived", target=period)
        return Response(self.get_serializer(period).data)


class IncidentMembershipViewSet(viewsets.ModelViewSet):
    queryset = IncidentMembership.objects.all()
    serializer_class = IncidentMembershipSerializer
    permission_classes = [PolicyPermission]
    policy_actions = {
        "list": MEMBERSHIP_MANAGE,
        "retrieve": MEMBERSHIP_MANAGE,
        "create": MEMBERSHIP_MANAGE,
        "update": MEMBERSHIP_MANAGE,
        "partial_update": MEMBERSHIP_MANAGE,
    }

    def get_queryset(self):
        queryset = IncidentMembership.objects.select_related("incident", "user", "assigned_by")
        if role_for_user(self.request.user) == Role.ADMINISTRATOR:
            return queryset
        return queryset.filter(
            incident__memberships__user=self.request.user,
            incident__memberships__is_active=True,
        ).distinct()

    def perform_create(self, serializer):
        incident = serializer.validated_data["incident"]
        if not user_has_permission(self.request.user, MEMBERSHIP_MANAGE, incident):
            raise PermissionDenied("Your incident role cannot manage memberships.")
        membership = serializer.save(assigned_by=self.request.user)
        record_event(
            actor=self.request.user,
            action="incident_membership.created",
            target=membership,
            details={
                "incident_id": str(incident.id),
                "user_id": membership.user_id,
                "role": membership.role,
            },
        )

    def perform_update(self, serializer):
        membership = serializer.save()
        record_event(
            actor=self.request.user,
            action="incident_membership.updated",
            target=membership,
            details={"changed_fields": sorted(serializer.validated_data)},
        )

    def destroy(self, request, *args, **kwargs):
        raise MethodNotAllowed("DELETE", detail="Deactivate memberships instead of deleting them.")
