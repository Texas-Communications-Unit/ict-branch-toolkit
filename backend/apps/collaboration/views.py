from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status, viewsets
from rest_framework.exceptions import MethodNotAllowed, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.accounts.permissions import PolicyPermission
from apps.accounts.policy import (
    ACCOUNT_MANAGE,
    PLAN_EDIT,
    PLAN_VIEW,
    role_for_user,
    user_has_permission,
)
from apps.audit.services import record_event
from apps.plans.models import PlanRevision

from .models import (
    CollaborationChange,
    CollaborationResolution,
    PresenceLease,
    SensitiveFieldRule,
)
from .serializers import (
    CollaborationChangeSerializer,
    CollaborationMutationSerializer,
    ConflictResolutionSerializer,
    PresenceHeartbeatSerializer,
    PresenceLeaseSerializer,
    SensitiveFieldRuleSerializer,
)
from .services import apply_mutation


def _revision_for(user, revision_id, permission):
    try:
        revision = PlanRevision.objects.select_related("plan__incident").get(pk=revision_id)
    except PlanRevision.DoesNotExist as exc:
        raise ValidationError({"revision": "Revision not found."}) from exc
    if not user_has_permission(user, permission, revision.plan.incident):
        raise PermissionDenied("Your current incident role does not permit this action.")
    return revision


class CollaborationMutationView(APIView):
    @extend_schema(
        request=CollaborationMutationSerializer,
        responses={
            status.HTTP_200_OK: CollaborationChangeSerializer,
            status.HTTP_400_BAD_REQUEST: CollaborationChangeSerializer,
            status.HTTP_409_CONFLICT: CollaborationChangeSerializer,
        },
    )
    def post(self, request):
        serializer = CollaborationMutationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        _revision_for(request.user, payload["revision"], PLAN_EDIT)
        change = apply_mutation(actor=request.user, request=request, payload=payload)
        response_status = {
            CollaborationChange.Disposition.SAVED: status.HTTP_200_OK,
            CollaborationChange.Disposition.CONFLICT: status.HTTP_409_CONFLICT,
            CollaborationChange.Disposition.REJECTED: status.HTTP_400_BAD_REQUEST,
        }[change.disposition]
        return Response(
            CollaborationChangeSerializer(change, context={"request": request}).data,
            status=response_status,
        )


class CollaborationChangeListView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter(
                "revision",
                OpenApiTypes.UUID,
                OpenApiParameter.QUERY,
                required=True,
            )
        ],
        responses=CollaborationChangeSerializer(many=True),
    )
    def get(self, request):
        revision_id = request.query_params.get("revision")
        if not revision_id:
            raise ValidationError({"revision": "A revision query parameter is required."})
        revision = _revision_for(request.user, revision_id, PLAN_VIEW)
        changes = (
            CollaborationChange.objects.filter(revision=revision)
            .select_related("incident", "actor")
            .prefetch_related("resolution")
            .order_by("-created_at")[: settings.ICT_COLLABORATION_HISTORY_LIMIT]
        )
        return Response(
            CollaborationChangeSerializer(
                changes,
                many=True,
                context={"request": request},
            ).data
        )


class ConflictResolutionView(APIView):
    @extend_schema(
        request=ConflictResolutionSerializer,
        responses={status.HTTP_201_CREATED: CollaborationChangeSerializer},
    )
    @transaction.atomic
    def post(self, request, change_id):
        try:
            conflict = (
                CollaborationChange.objects.select_for_update()
                .select_related("revision__plan__incident")
                .get(pk=change_id)
            )
        except CollaborationChange.DoesNotExist as exc:
            raise ValidationError({"conflict": "Conflict not found."}) from exc
        if not user_has_permission(request.user, PLAN_EDIT, conflict.incident):
            raise PermissionDenied("Your current incident role cannot resolve this conflict.")
        if conflict.disposition != CollaborationChange.Disposition.CONFLICT:
            raise ValidationError({"conflict": "Only a retained conflict can be resolved."})
        if hasattr(conflict, "resolution"):
            raise ValidationError({"conflict": "This conflict already has a resolution."})
        serializer = ConflictResolutionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        replacement = None
        replacement_id = serializer.validated_data.get("replacement_change")
        if replacement_id:
            try:
                replacement = CollaborationChange.objects.get(
                    pk=replacement_id,
                    revision=conflict.revision,
                    actor=request.user,
                    disposition=CollaborationChange.Disposition.SAVED,
                )
            except CollaborationChange.DoesNotExist as exc:
                raise ValidationError(
                    {"replacement_change": "Select your saved change from the same revision."}
                ) from exc
        resolution = CollaborationResolution.objects.create(
            conflict=conflict,
            decision=serializer.validated_data["decision"],
            explanation=serializer.validated_data["explanation"],
            resolved_by=request.user,
            replacement_change=replacement,
        )
        record_event(
            actor=request.user,
            action="collaboration.conflict_resolved",
            target=resolution,
            details={
                "conflict_id": str(conflict.id),
                "decision": resolution.decision,
                "replacement_change_id": (str(replacement.id) if replacement else None),
            },
        )
        return Response(
            CollaborationChangeSerializer(
                conflict,
                context={"request": request},
            ).data,
            status=status.HTTP_201_CREATED,
        )


class PresenceView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter(
                "revision",
                OpenApiTypes.UUID,
                OpenApiParameter.QUERY,
                required=True,
            ),
            OpenApiParameter("section", OpenApiTypes.STR, OpenApiParameter.QUERY),
        ],
        responses=PresenceLeaseSerializer(many=True),
    )
    def get(self, request):
        revision_id = request.query_params.get("revision")
        if not revision_id:
            raise ValidationError({"revision": "A revision query parameter is required."})
        revision = _revision_for(request.user, revision_id, PLAN_VIEW)
        PresenceLease.objects.filter(expires_at__lte=timezone.now()).delete()
        leases = PresenceLease.objects.filter(revision=revision, expires_at__gt=timezone.now())
        section = request.query_params.get("section")
        if section:
            leases = leases.filter(section=section)
        return Response(
            PresenceLeaseSerializer(
                leases.select_related("user"),
                many=True,
                context={"request": request},
            ).data
        )

    @extend_schema(
        request=PresenceHeartbeatSerializer,
        responses={
            status.HTTP_200_OK: PresenceLeaseSerializer,
            status.HTTP_201_CREATED: PresenceLeaseSerializer,
        },
    )
    @transaction.atomic
    def post(self, request):
        serializer = PresenceHeartbeatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        revision = _revision_for(request.user, data["revision"], PLAN_VIEW)
        if data["mode"] == PresenceLease.Mode.EDITING and not user_has_permission(
            request.user,
            PLAN_EDIT,
            revision.plan.incident,
        ):
            raise PermissionDenied("Your current incident role cannot claim editing presence.")
        expires_at = timezone.now() + timedelta(
            seconds=settings.ICT_COLLABORATION_PRESENCE_TTL_SECONDS
        )
        lease, created = PresenceLease.objects.select_for_update().get_or_create(
            revision=revision,
            user=request.user,
            device_id=data["device_id"],
            section=data["section"],
            defaults={
                "incident": revision.plan.incident,
                "mode": data["mode"],
                "expires_at": expires_at,
            },
        )
        if not created:
            lease.mode = data["mode"]
            lease.expires_at = expires_at
            lease.sequence += 1
            lease.save(update_fields=["mode", "expires_at", "sequence", "last_seen_at"])
        PresenceLease.objects.filter(expires_at__lte=timezone.now()).delete()
        return Response(
            PresenceLeaseSerializer(lease, context={"request": request}).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "revision",
                OpenApiTypes.UUID,
                OpenApiParameter.QUERY,
                required=True,
            ),
            OpenApiParameter(
                "device_id",
                OpenApiTypes.UUID,
                OpenApiParameter.QUERY,
                required=True,
            ),
            OpenApiParameter("section", OpenApiTypes.STR, OpenApiParameter.QUERY),
        ],
        request=None,
        responses={status.HTTP_204_NO_CONTENT: None},
    )
    def delete(self, request):
        revision_id = request.query_params.get("revision")
        device_id = request.query_params.get("device_id")
        section = request.query_params.get("section", "ics205")
        if not revision_id or not device_id:
            raise ValidationError(
                {"detail": "revision and device_id query parameters are required."}
            )
        revision = _revision_for(request.user, revision_id, PLAN_VIEW)
        PresenceLease.objects.filter(
            revision=revision,
            user=request.user,
            device_id=device_id,
            section=section,
        ).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SensitiveFieldRuleViewSet(viewsets.ModelViewSet):
    queryset = SensitiveFieldRule.objects.select_related("incident", "created_by", "updated_by")
    serializer_class = SensitiveFieldRuleSerializer
    permission_classes = [PolicyPermission]
    policy_actions = {
        "list": ACCOUNT_MANAGE,
        "retrieve": ACCOUNT_MANAGE,
        "create": ACCOUNT_MANAGE,
        "update": ACCOUNT_MANAGE,
        "partial_update": ACCOUNT_MANAGE,
    }

    def get_queryset(self):
        if role_for_user(self.request.user) != Role.ADMINISTRATOR:
            return SensitiveFieldRule.objects.none()
        queryset = super().get_queryset()
        incident_id = self.request.query_params.get("incident")
        return queryset.filter(incident_id=incident_id) if incident_id else queryset

    def perform_create(self, serializer):
        rule = serializer.save(created_by=self.request.user, updated_by=self.request.user)
        record_event(
            actor=self.request.user,
            action="collaboration.sensitive_field_rule_created",
            target=rule,
            details={"field_name": rule.field_name, "version": rule.version},
        )

    def perform_update(self, serializer):
        rule = serializer.save(updated_by=self.request.user)
        record_event(
            actor=self.request.user,
            action="collaboration.sensitive_field_rule_updated",
            target=rule,
            details={"field_name": rule.field_name, "version": rule.version},
        )

    def destroy(self, request, *args, **kwargs):
        raise MethodNotAllowed(
            "DELETE",
            detail="Sensitive-field rules are retained. Supersede the existing rule.",
        )
