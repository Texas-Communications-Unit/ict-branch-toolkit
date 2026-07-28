from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.accounts.permissions import PolicyPermission
from apps.accounts.policy import RF_APPROVE, RF_EDIT, RF_VIEW, role_for_user, user_has_permission
from apps.audit.services import record_event

from .models import DeconflictionAnalysis
from .serializers import (
    CreateDeconflictionAnalysisSerializer,
    DeconflictionAnalysisSerializer,
    DeconflictionRuleSetStatusSerializer,
)
from .services import (
    approve_deconfliction_analysis,
    create_deconfliction_analysis,
    deconfliction_status,
)


class DeconflictionRuleSetStatusView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: DeconflictionRuleSetStatusSerializer})
    def get(self, request):
        return Response(deconfliction_status())


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter(
                name="incident",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description="Limit results to one incident.",
            )
        ]
    ),
    create=extend_schema(
        request=CreateDeconflictionAnalysisSerializer,
        responses={201: DeconflictionAnalysisSerializer},
    ),
)
class DeconflictionAnalysisViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = DeconflictionAnalysis.objects.none()
    serializer_class = DeconflictionAnalysisSerializer
    permission_classes = [PolicyPermission]
    policy_actions = {
        "list": RF_VIEW,
        "retrieve": RF_VIEW,
        "create": RF_EDIT,
        "approve": RF_APPROVE,
    }

    def get_queryset(self):
        queryset = DeconflictionAnalysis.objects.select_related(
            "incident",
            "approved_revision__plan",
            "created_by",
            "approved_by",
        )
        if role_for_user(self.request.user) != Role.ADMINISTRATOR:
            queryset = queryset.filter(
                incident__memberships__user=self.request.user,
                incident__memberships__is_active=True,
            ).distinct()
        incident_id = self.request.query_params.get("incident")
        return queryset.filter(incident_id=incident_id) if incident_id else queryset

    def create(self, request, *args, **kwargs):
        input_serializer = CreateDeconflictionAnalysisSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        incident = input_serializer.validated_data["incident"]
        if not user_has_permission(request.user, RF_EDIT, incident):
            raise PermissionDenied("Your incident role cannot create deconfliction analyses.")
        analysis = create_deconfliction_analysis(
            incident=incident,
            approved_revision=input_serializer.validated_data["approved_revision"],
            active_resources=input_serializer.validated_data.get("active_resources", []),
            actor=request.user,
        )
        record_event(
            actor=request.user,
            action="deconfliction_analysis.created",
            target=analysis,
            details={
                "incident_id": str(analysis.incident_id),
                "approved_revision_id": str(analysis.approved_revision_id),
                "rule_set_version": analysis.rule_set_version,
                "selected_active_resource_count": len(
                    analysis.input_snapshot["selected_active_resources"]
                ),
                "warning_count": analysis.warning_count,
                "input_sha256": analysis.input_sha256,
                "result_sha256": analysis.result_sha256,
            },
        )
        output = self.get_serializer(analysis)
        return Response(output.data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={200: DeconflictionAnalysisSerializer})
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        analysis = self.get_object()
        if not user_has_permission(request.user, RF_APPROVE, analysis.incident):
            raise PermissionDenied("Your incident role cannot approve deconfliction analyses.")
        approved = approve_deconfliction_analysis(analysis, actor=request.user)
        record_event(
            actor=request.user,
            action="deconfliction_analysis.approved",
            target=approved,
            details={
                "incident_id": str(approved.incident_id),
                "approved_revision_id": str(approved.approved_revision_id),
                "rule_set_version": approved.rule_set_version,
                "warning_count": approved.warning_count,
                "input_sha256": approved.input_sha256,
                "result_sha256": approved.result_sha256,
            },
        )
        return Response(self.get_serializer(approved).data)
