import hashlib

from django.db.models import Prefetch
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.accounts.permissions import PolicyPermission
from apps.accounts.policy import (
    PLAN_EXPORT,
    RF_APPROVE,
    RF_EDIT,
    RF_VIEW,
    role_for_user,
    user_has_permission,
)
from apps.audit.models import AuditEvent
from apps.audit.serializers import ExportDigestVerificationRequestSerializer
from apps.audit.services import record_event

from .calibration import (
    approve_calibration_set,
    calibration_status,
    create_calibration_set,
    create_field_observation,
    review_field_observation,
)
from .coverage import (
    approve_coverage_estimate,
    coverage_engine_status,
    create_coverage_estimate,
)
from .directional import (
    approve_directional_analysis,
    create_directional_analysis,
    directional_analysis_status,
)
from .elevation import provider_status
from .haat import (
    approve_haat_calculation,
    create_haat_calculation,
    retry_haat_calculation,
)
from .models import (
    CalibrationSet,
    CoverageEstimate,
    DirectionalCoverageAnalysis,
    ElevationSnapshot,
    FieldObservation,
    HAATCalculation,
    Phase2ValidationBundle,
    RFAnalysisInputSnapshot,
    SubscriberProfile,
    SubscriberProfileVersion,
    TerrainAnalysis,
)
from .phase2_validation import (
    approve_validation_bundle,
    cancel_validation_bundle,
    queue_validation_bundle,
    run_validation_bundle,
    sha256_bytes,
    validation_export_bytes,
    validation_status,
)
from .serializers import (
    CalibrationSetSerializer,
    CoverageEstimateSerializer,
    CreateCalibrationSetSerializer,
    CreateCoverageEstimateSerializer,
    CreateDirectionalCoverageAnalysisSerializer,
    CreateFieldObservationSerializer,
    CreateHAATCalculationSerializer,
    CreatePhase2ValidationBundleSerializer,
    CreateRFAnalysisInputSnapshotSerializer,
    CreateTerrainAnalysisSerializer,
    DirectionalCoverageAnalysisSerializer,
    ElevationSnapshotSerializer,
    FieldObservationSerializer,
    HAATCalculationSerializer,
    Phase2ValidationBundleSerializer,
    ReviewFieldObservationSerializer,
    RFAnalysisInputSnapshotSerializer,
    SubscriberProfileSerializer,
    SubscriberProfileVersionSerializer,
    TerrainAnalysisSerializer,
    TerrainAnalysisStatusSerializer,
)
from .services import (
    VERSION_EDITABLE_FIELDS,
    approve_version,
    archive_analysis_snapshot,
    copy_version,
    create_analysis_snapshot,
)
from .terrain import (
    approve_terrain_analysis,
    cancel_terrain_analysis,
    queue_terrain_analysis,
    run_terrain_analysis,
    terrain_status,
)


def scoped_to_incidents(queryset, user, incident_path="incident"):
    if role_for_user(user) == Role.ADMINISTRATOR:
        return queryset
    return queryset.filter(
        **{
            f"{incident_path}__memberships__user": user,
            f"{incident_path}__memberships__is_active": True,
        }
    ).distinct()


class TerrainAnalysisPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = "page_size"
    max_page_size = 10


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
    )
)
class SubscriberProfileViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = SubscriberProfile.objects.none()
    serializer_class = SubscriberProfileSerializer
    permission_classes = [PolicyPermission]
    policy_actions = {
        "list": RF_VIEW,
        "retrieve": RF_VIEW,
        "create": RF_EDIT,
        "update": RF_EDIT,
        "partial_update": RF_EDIT,
        "archive": RF_EDIT,
    }

    def get_queryset(self):
        queryset = scoped_to_incidents(
            SubscriberProfile.objects.filter(archived_at__isnull=True)
            .select_related("incident", "created_by")
            .prefetch_related(
                Prefetch(
                    "versions",
                    queryset=SubscriberProfileVersion.objects.select_related(
                        "created_by",
                        "approved_by",
                    ),
                )
            ),
            self.request.user,
        )
        incident_id = self.request.query_params.get("incident")
        return queryset.filter(incident_id=incident_id) if incident_id else queryset

    def perform_create(self, serializer):
        incident = serializer.validated_data["incident"]
        if incident.archived_at:
            raise PermissionDenied("Subscriber profiles cannot be added to an archived incident.")
        if not user_has_permission(self.request.user, RF_EDIT, incident):
            raise PermissionDenied("Your incident role cannot create subscriber profiles.")
        profile = serializer.save(created_by=self.request.user)
        version = profile.versions.get(number=1)
        record_event(
            actor=self.request.user,
            action="subscriber_profile.created",
            target=profile,
            details={
                "changed_fields": [
                    "created_by",
                    "description",
                    "incident",
                    "name",
                    "profile_type",
                ]
            },
        )
        record_event(
            actor=self.request.user,
            action="subscriber_profile_version.created",
            target=version,
            details={
                "changed_fields": sorted(
                    {"created_by", "number", "profile", "status"}
                    | set(serializer.validated_data["initial_version"])
                )
            },
        )

    def perform_update(self, serializer):
        profile = serializer.save()
        record_event(
            actor=self.request.user,
            action="subscriber_profile.updated",
            target=profile,
            details={"changed_fields": sorted(serializer.validated_data)},
        )

    @extend_schema(request=None, responses={200: SubscriberProfileSerializer})
    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        profile = self.get_object()
        profile.archived_at = timezone.now()
        profile.save(update_fields=["archived_at", "updated_at"])
        record_event(
            actor=request.user,
            action="subscriber_profile.archived",
            target=profile,
            details={"changed_fields": ["archived_at"]},
        )
        return Response(self.get_serializer(profile).data)


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter(
                name="profile",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description="Limit results to one subscriber profile.",
            )
        ]
    )
)
class SubscriberProfileVersionViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = SubscriberProfileVersion.objects.none()
    http_method_names = ["get", "patch", "post", "head", "options"]
    serializer_class = SubscriberProfileVersionSerializer
    permission_classes = [PolicyPermission]
    policy_actions = {
        "list": RF_VIEW,
        "retrieve": RF_VIEW,
        "update": RF_EDIT,
        "partial_update": RF_EDIT,
        "copy": RF_EDIT,
        "approve": RF_APPROVE,
        "create_snapshot": RF_APPROVE,
    }

    def get_queryset(self):
        queryset = scoped_to_incidents(
            SubscriberProfileVersion.objects.filter(
                profile__archived_at__isnull=True
            ).select_related(
                "profile__incident",
                "profile__created_by",
                "created_by",
                "approved_by",
            ),
            self.request.user,
            "profile__incident",
        )
        profile_id = self.request.query_params.get("profile")
        return queryset.filter(profile_id=profile_id) if profile_id else queryset

    def perform_update(self, serializer):
        version = serializer.save()
        record_event(
            actor=self.request.user,
            action="subscriber_profile_version.updated",
            target=version,
            details={"changed_fields": sorted(serializer.validated_data)},
        )

    @extend_schema(request=None, responses={201: SubscriberProfileVersionSerializer})
    @action(detail=True, methods=["post"])
    def copy(self, request, pk=None):
        source = self.get_object()
        copied = copy_version(source, request.user)
        record_event(
            actor=request.user,
            action="subscriber_profile_version.copied",
            target=copied,
            details={
                "changed_fields": sorted(
                    {"created_by", "number", "profile", "status"}
                    | set(VERSION_EDITABLE_FIELDS)
                    | {"erp_calculation_path"}
                )
            },
        )
        return Response(self.get_serializer(copied).data, status=201)

    @extend_schema(request=None, responses={200: SubscriberProfileVersionSerializer})
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        version = approve_version(self.get_object(), request.user)
        record_event(
            actor=request.user,
            action="subscriber_profile_version.approved",
            target=version,
            details={
                "changed_fields": [
                    "approved_at",
                    "approved_by",
                    "input_sha256",
                    "input_snapshot",
                    "status",
                ]
            },
        )
        return Response(self.get_serializer(version).data)

    @extend_schema(
        request=CreateRFAnalysisInputSnapshotSerializer,
        responses={201: RFAnalysisInputSnapshotSerializer},
    )
    @action(detail=True, methods=["post"])
    def create_snapshot(self, request, pk=None):
        version = self.get_object()
        request_serializer = CreateRFAnalysisInputSnapshotSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        snapshot = create_analysis_snapshot(
            version,
            label=request_serializer.validated_data["label"],
            actor=request.user,
        )
        record_event(
            actor=request.user,
            action="rf_analysis_input_snapshot.created",
            target=snapshot,
            details={
                "changed_fields": [
                    "approved_at",
                    "approved_by",
                    "created_by",
                    "incident",
                    "input_sha256",
                    "input_snapshot",
                    "label",
                    "profile_version",
                ]
            },
        )
        return Response(RFAnalysisInputSnapshotSerializer(snapshot).data, status=201)


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
    )
)
class RFAnalysisInputSnapshotViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = RFAnalysisInputSnapshot.objects.none()
    serializer_class = RFAnalysisInputSnapshotSerializer
    permission_classes = [PolicyPermission]
    policy_actions = {
        "list": RF_VIEW,
        "retrieve": RF_VIEW,
        "archive": RF_APPROVE,
    }

    def get_queryset(self):
        queryset = scoped_to_incidents(
            RFAnalysisInputSnapshot.objects.filter(archived_at__isnull=True).select_related(
                "incident",
                "profile_version__profile",
                "created_by",
                "approved_by",
            ),
            self.request.user,
        )
        incident_id = self.request.query_params.get("incident")
        return queryset.filter(incident_id=incident_id) if incident_id else queryset

    @extend_schema(request=None, responses={200: RFAnalysisInputSnapshotSerializer})
    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        snapshot = archive_analysis_snapshot(self.get_object())
        record_event(
            actor=request.user,
            action="rf_analysis_input_snapshot.archived",
            target=snapshot,
            details={"changed_fields": ["archived_at"]},
        )
        return Response(self.get_serializer(snapshot).data)


class ElevationProviderStatusView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        return Response(provider_status())


class CoverageEngineStatusView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        return Response(coverage_engine_status())


class ElevationSnapshotViewSet(
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = ElevationSnapshot.objects.none()
    serializer_class = ElevationSnapshotSerializer
    permission_classes = [PolicyPermission]
    policy_actions = {"retrieve": RF_VIEW}

    def get_queryset(self):
        return scoped_to_incidents(
            ElevationSnapshot.objects.select_related(
                "incident",
                "site",
                "created_by",
            ),
            self.request.user,
        )


class HAATCalculationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = HAATCalculation.objects.none()
    serializer_class = HAATCalculationSerializer
    permission_classes = [PolicyPermission]
    policy_actions = {
        "list": RF_VIEW,
        "retrieve": RF_VIEW,
        "create": RF_EDIT,
        "retry": RF_EDIT,
        "approve": RF_APPROVE,
    }

    def get_queryset(self):
        queryset = scoped_to_incidents(
            HAATCalculation.objects.select_related(
                "incident",
                "site",
                "profile_version__profile",
                "rf_input_snapshot",
                "elevation_snapshot",
                "created_by",
                "approved_by",
                "supersedes",
            ),
            self.request.user,
        )
        incident_id = self.request.query_params.get("incident")
        return queryset.filter(incident_id=incident_id) if incident_id else queryset

    def get_serializer_class(self):
        if self.action == "create":
            return CreateHAATCalculationSerializer
        return HAATCalculationSerializer

    @extend_schema(
        request=CreateHAATCalculationSerializer,
        responses={201: HAATCalculationSerializer},
    )
    def create(self, request, *args, **kwargs):
        request_serializer = CreateHAATCalculationSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        values = request_serializer.validated_data
        site = values["site"]
        if not user_has_permission(request.user, RF_EDIT, site.incident):
            raise PermissionDenied("Your incident role cannot calculate HAAT.")
        calculation, cache_hit = create_haat_calculation(
            site=site,
            rf_input_snapshot=values["rf_input_snapshot"],
            actor=request.user,
            radial_count=values["radial_count"],
            start_azimuth_deg=values["start_azimuth_deg"],
            sampling_interval_m=values["sampling_interval_m"],
            inner_distance_m=values["inner_distance_m"],
            outer_distance_m=values["outer_distance_m"],
            rounding_m=values["rounding_m"],
            force_refresh=values["force_refresh"],
        )
        record_event(
            actor=request.user,
            action="haat_calculation.created",
            target=calculation,
            details={
                "changed_fields": [
                    "algorithm_snapshot",
                    "calculation_state",
                    "elevation_snapshot",
                    "result_sha256",
                    "result_snapshot",
                    "site",
                    "rf_input_snapshot",
                ],
                "cache_hit": cache_hit,
            },
        )
        return Response(
            HAATCalculationSerializer(calculation).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(request=None, responses={201: HAATCalculationSerializer})
    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        source = self.get_object()
        calculation, cache_hit = retry_haat_calculation(source, actor=request.user)
        record_event(
            actor=request.user,
            action="haat_calculation.retried",
            target=calculation,
            details={
                "changed_fields": [
                    "elevation_snapshot",
                    "result_sha256",
                    "result_snapshot",
                    "supersedes",
                ],
                "cache_hit": cache_hit,
                "superseded_calculation_id": str(source.id),
            },
        )
        return Response(
            HAATCalculationSerializer(calculation).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(request=None, responses={200: HAATCalculationSerializer})
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        calculation = approve_haat_calculation(self.get_object(), actor=request.user)
        record_event(
            actor=request.user,
            action="haat_calculation.approved",
            target=calculation,
            details={
                "changed_fields": ["approved_at", "approved_by", "status"],
                "result_sha256": calculation.result_sha256,
            },
        )
        return Response(HAATCalculationSerializer(calculation).data)


class CoverageEstimateViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = CoverageEstimate.objects.none()
    serializer_class = CoverageEstimateSerializer
    permission_classes = [PolicyPermission]
    policy_actions = {
        "list": RF_VIEW,
        "retrieve": RF_VIEW,
        "create": RF_EDIT,
        "approve": RF_APPROVE,
    }

    def get_queryset(self):
        queryset = scoped_to_incidents(
            CoverageEstimate.objects.select_related(
                "incident",
                "site",
                "rf_input_snapshot",
                "haat_calculation",
                "created_by",
                "approved_by",
            ),
            self.request.user,
        )
        incident_id = self.request.query_params.get("incident")
        return queryset.filter(incident_id=incident_id) if incident_id else queryset

    def get_serializer_class(self):
        if self.action == "create":
            return CreateCoverageEstimateSerializer
        return CoverageEstimateSerializer

    @extend_schema(
        request=CreateCoverageEstimateSerializer,
        responses={201: CoverageEstimateSerializer},
    )
    def create(self, request, *args, **kwargs):
        request_serializer = CreateCoverageEstimateSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        values = request_serializer.validated_data
        haat_calculation = values["haat_calculation"]
        if not user_has_permission(request.user, RF_EDIT, haat_calculation.incident):
            raise PermissionDenied("Your incident role cannot create coverage estimates.")
        estimate = create_coverage_estimate(
            haat_calculation=haat_calculation,
            environment=values["environment"],
            preset=values["preset"],
            actor=request.user,
        )
        record_event(
            actor=request.user,
            action="coverage_estimate.created",
            target=estimate,
            details={
                "changed_fields": [
                    "calculation_state",
                    "engine_version",
                    "environment",
                    "input_sha256",
                    "model_snapshot",
                    "preset_version",
                    "result_sha256",
                    "result_snapshot",
                ],
                "source_rf_input_sha256": estimate.rf_input_snapshot.input_sha256,
                "source_haat_result_sha256": estimate.haat_calculation.result_sha256,
            },
        )
        return Response(
            CoverageEstimateSerializer(estimate).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(request=None, responses={200: CoverageEstimateSerializer})
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        estimate = approve_coverage_estimate(self.get_object(), actor=request.user)
        record_event(
            actor=request.user,
            action="coverage_estimate.approved",
            target=estimate,
            details={
                "changed_fields": ["approved_at", "approved_by", "status"],
                "result_sha256": estimate.result_sha256,
            },
        )
        return Response(CoverageEstimateSerializer(estimate).data)


class DirectionalCoverageAnalysisViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = DirectionalCoverageAnalysis.objects.none()
    serializer_class = DirectionalCoverageAnalysisSerializer
    permission_classes = [PolicyPermission]
    policy_actions = {
        "list": RF_VIEW,
        "retrieve": RF_VIEW,
        "create": RF_EDIT,
        "approve": RF_APPROVE,
    }

    def get_queryset(self):
        queryset = scoped_to_incidents(
            DirectionalCoverageAnalysis.objects.select_related(
                "incident",
                "site",
                "infrastructure_rf_input_snapshot",
                "subscriber_rf_input_snapshot__profile_version__profile",
                "haat_calculation",
                "created_by",
                "approved_by",
            ),
            self.request.user,
        )
        incident_id = self.request.query_params.get("incident")
        return queryset.filter(incident_id=incident_id) if incident_id else queryset

    def get_serializer_class(self):
        if self.action == "create":
            return CreateDirectionalCoverageAnalysisSerializer
        return DirectionalCoverageAnalysisSerializer

    @extend_schema(
        request=CreateDirectionalCoverageAnalysisSerializer,
        responses={201: DirectionalCoverageAnalysisSerializer},
    )
    def create(self, request, *args, **kwargs):
        request_serializer = CreateDirectionalCoverageAnalysisSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        values = request_serializer.validated_data
        haat_calculation = values["haat_calculation"]
        if not user_has_permission(request.user, RF_EDIT, haat_calculation.incident):
            raise PermissionDenied(
                "Your incident role cannot create directional coverage analyses."
            )
        analysis = create_directional_analysis(
            haat_calculation=haat_calculation,
            subscriber_rf_input_snapshot=values["subscriber_rf_input_snapshot"],
            environment=values["environment"],
            preset=values["preset"],
            actor=request.user,
        )
        record_event(
            actor=request.user,
            action="directional_coverage_analysis.created",
            target=analysis,
            details={
                "changed_fields": [
                    "calculation_state",
                    "engine_version",
                    "environment",
                    "input_sha256",
                    "limiting_path",
                    "model_snapshot",
                    "preset_version",
                    "result_sha256",
                    "result_snapshot",
                    "rule_version",
                ],
                "infrastructure_input_sha256": (
                    analysis.infrastructure_rf_input_snapshot.input_sha256
                ),
                "subscriber_input_sha256": (analysis.subscriber_rf_input_snapshot.input_sha256),
                "source_haat_result_sha256": analysis.haat_calculation.result_sha256,
            },
        )
        return Response(
            DirectionalCoverageAnalysisSerializer(analysis).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(request=None, responses={200: DirectionalCoverageAnalysisSerializer})
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        analysis = approve_directional_analysis(self.get_object(), actor=request.user)
        record_event(
            actor=request.user,
            action="directional_coverage_analysis.approved",
            target=analysis,
            details={
                "changed_fields": ["approved_at", "approved_by", "status"],
                "result_sha256": analysis.result_sha256,
            },
        )
        return Response(DirectionalCoverageAnalysisSerializer(analysis).data)


class DirectionalAnalysisStatusView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        return Response(directional_analysis_status())


class FieldObservationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = FieldObservation.objects.none()
    serializer_class = FieldObservationSerializer
    permission_classes = [PolicyPermission]
    policy_actions = {
        "list": RF_VIEW,
        "retrieve": RF_VIEW,
        "create": RF_EDIT,
        "review": RF_APPROVE,
    }

    def get_queryset(self):
        queryset = scoped_to_incidents(
            FieldObservation.objects.select_related(
                "incident",
                "infrastructure_rf_input_snapshot",
                "subscriber_rf_input_snapshot",
                "coverage_estimate",
                "directional_analysis",
                "supersedes",
                "created_by",
            ).prefetch_related("reviews", "superseded_by"),
            self.request.user,
        )
        incident_id = self.request.query_params.get("incident")
        return queryset.filter(incident_id=incident_id) if incident_id else queryset

    def get_serializer_class(self):
        if self.action == "create":
            return CreateFieldObservationSerializer
        return FieldObservationSerializer

    @extend_schema(
        request=CreateFieldObservationSerializer,
        responses={201: FieldObservationSerializer},
    )
    def create(self, request, *args, **kwargs):
        request_serializer = CreateFieldObservationSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        values = request_serializer.validated_data
        incident = values["incident"]
        if not user_has_permission(request.user, RF_EDIT, incident):
            raise PermissionDenied("Your incident role cannot record field observations.")
        observation = create_field_observation(values=values, actor=request.user)
        record_event(
            actor=request.user,
            action="field_observation.created",
            target=observation,
            details={
                "changed_fields": [
                    "classification",
                    "evidence_type",
                    "input_sha256",
                    "location_precision",
                    "source_revision",
                ],
                "input_sha256": observation.input_sha256,
                "supersedes_id": (
                    str(observation.supersedes_id) if observation.supersedes_id else None
                ),
            },
        )
        return Response(
            FieldObservationSerializer(observation).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        request=ReviewFieldObservationSerializer,
        responses={200: FieldObservationSerializer},
    )
    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        observation = self.get_object()
        request_serializer = ReviewFieldObservationSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        values = request_serializer.validated_data
        review = review_field_observation(
            observation,
            decision=values["decision"],
            reason=values["reason"],
            actor=request.user,
        )
        record_event(
            actor=request.user,
            action=f"field_observation.{review.decision}",
            target=observation,
            details={
                "changed_fields": ["current_review_state"],
                "review_evidence_sha256": review.evidence_sha256,
            },
        )
        observation = self.get_queryset().get(pk=observation.pk)
        return Response(FieldObservationSerializer(observation).data)


class CalibrationSetViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = CalibrationSet.objects.none()
    serializer_class = CalibrationSetSerializer
    permission_classes = [PolicyPermission]
    policy_actions = {
        "list": RF_VIEW,
        "retrieve": RF_VIEW,
        "create": RF_EDIT,
        "approve": RF_APPROVE,
    }

    def get_queryset(self):
        queryset = scoped_to_incidents(
            CalibrationSet.objects.select_related(
                "incident",
                "created_by",
                "approved_by",
            ).prefetch_related("observations", "observation_links"),
            self.request.user,
        )
        incident_id = self.request.query_params.get("incident")
        return queryset.filter(incident_id=incident_id) if incident_id else queryset

    def get_serializer_class(self):
        if self.action == "create":
            return CreateCalibrationSetSerializer
        return CalibrationSetSerializer

    @extend_schema(
        request=CreateCalibrationSetSerializer,
        responses={201: CalibrationSetSerializer},
    )
    def create(self, request, *args, **kwargs):
        request_serializer = CreateCalibrationSetSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        values = request_serializer.validated_data
        incident = values["incident"]
        if not user_has_permission(request.user, RF_EDIT, incident):
            raise PermissionDenied("Your incident role cannot create calibration sets.")
        calibration_set = create_calibration_set(
            incident=incident,
            name=values["name"],
            observations=list(values["observations"]),
            baseline_preset=values["baseline_preset"],
            baseline_preset_version=values["baseline_preset_version"],
            parameters=values["parameters"],
            actor=request.user,
        )
        record_event(
            actor=request.user,
            action="calibration_set.created",
            target=calibration_set,
            details={
                "changed_fields": [
                    "algorithm_version",
                    "calculation_state",
                    "observation_sha256",
                    "result_sha256",
                    "version",
                ],
                "observation_count": len(calibration_set.observation_snapshot),
                "observation_sha256": calibration_set.observation_sha256,
                "result_sha256": calibration_set.result_sha256,
            },
        )
        return Response(
            CalibrationSetSerializer(calibration_set).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(request=None, responses={200: CalibrationSetSerializer})
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        calibration_set = approve_calibration_set(self.get_object(), actor=request.user)
        record_event(
            actor=request.user,
            action="calibration_set.approved",
            target=calibration_set,
            details={
                "changed_fields": ["approved_at", "approved_by", "status"],
                "result_sha256": calibration_set.result_sha256,
            },
        )
        return Response(CalibrationSetSerializer(calibration_set).data)


class CalibrationStatusView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        return Response(calibration_status())


class Phase2ValidationBundleViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Phase2ValidationBundle.objects.none()
    serializer_class = Phase2ValidationBundleSerializer
    permission_classes = [PolicyPermission]
    policy_actions = {
        "list": RF_VIEW,
        "retrieve": RF_VIEW,
        "create": RF_EDIT,
        "run": RF_EDIT,
        "cancel": RF_EDIT,
        "retry": RF_EDIT,
        "approve": RF_APPROVE,
        "export": RF_APPROVE,
        "verify": RF_APPROVE,
    }

    def get_queryset(self):
        queryset = scoped_to_incidents(
            Phase2ValidationBundle.objects.select_related(
                "incident",
                "approved_revision__plan__incident",
                "approved_revision__plan__operational_period",
                "haat_calculation__elevation_snapshot",
                "haat_calculation__rf_input_snapshot",
                "coverage_estimate",
                "directional_analysis__infrastructure_rf_input_snapshot",
                "directional_analysis__subscriber_rf_input_snapshot",
                "calibration_set",
                "created_by",
                "approved_by",
                "supersedes",
            ).prefetch_related(
                "approved_revision__assignments__site_links",
                "approved_revision__relationships__assignments",
                "calibration_set__observation_links__observation__reviews",
            ),
            self.request.user,
        )
        incident_id = self.request.query_params.get("incident")
        return queryset.filter(incident_id=incident_id) if incident_id else queryset

    def get_serializer_class(self):
        if self.action == "create":
            return CreatePhase2ValidationBundleSerializer
        return Phase2ValidationBundleSerializer

    @extend_schema(
        request=CreatePhase2ValidationBundleSerializer,
        responses={201: Phase2ValidationBundleSerializer},
    )
    def create(self, request, *args, **kwargs):
        request_serializer = CreatePhase2ValidationBundleSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        values = request_serializer.validated_data
        incident = values["incident"]
        if not user_has_permission(request.user, RF_EDIT, incident):
            raise PermissionDenied("Your incident role cannot queue Phase 2 validation evidence.")
        bundle = queue_validation_bundle(actor=request.user, **values)
        record_event(
            actor=request.user,
            action="phase2_validation.queued",
            target=bundle,
            details={
                "approved_revision_id": str(bundle.approved_revision_id),
                "haat_result_sha256": bundle.haat_calculation.result_sha256,
                "coverage_result_sha256": bundle.coverage_estimate.result_sha256,
                "directional_result_sha256": bundle.directional_analysis.result_sha256,
                "calibration_result_sha256": bundle.calibration_set.result_sha256,
                "input_sha256": bundle.input_sha256,
                "validation_profile_version": bundle.validation_profile_version,
            },
        )
        return Response(
            Phase2ValidationBundleSerializer(bundle).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(request=None, responses={200: Phase2ValidationBundleSerializer})
    @action(detail=True, methods=["post"])
    def run(self, request, pk=None):
        bundle = run_validation_bundle(self.get_object())
        record_event(
            actor=request.user,
            action=(
                "phase2_validation.completed"
                if bundle.job_state == Phase2ValidationBundle.JobState.COMPLETE
                else "phase2_validation.failed"
            ),
            target=bundle,
            details={
                "job_state": bundle.job_state,
                "failure_code": bundle.failure_code,
                "input_sha256": bundle.input_sha256,
                "result_sha256": bundle.result_sha256,
                "validation_profile_version": bundle.validation_profile_version,
            },
        )
        return Response(Phase2ValidationBundleSerializer(bundle).data)

    @extend_schema(request=None, responses={200: Phase2ValidationBundleSerializer})
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        bundle = cancel_validation_bundle(self.get_object())
        record_event(
            actor=request.user,
            action="phase2_validation.cancelled",
            target=bundle,
            details={"job_state": bundle.job_state, "failure_code": bundle.failure_code},
        )
        return Response(Phase2ValidationBundleSerializer(bundle).data)

    @extend_schema(request=None, responses={201: Phase2ValidationBundleSerializer})
    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        source = self.get_object()
        if source.job_state not in {
            Phase2ValidationBundle.JobState.FAILED,
            Phase2ValidationBundle.JobState.CANCELLED,
        }:
            raise ValidationError("Only failed or cancelled validation work can be retried.")
        bundle = queue_validation_bundle(
            incident=source.incident,
            approved_revision=source.approved_revision,
            haat_calculation=source.haat_calculation,
            coverage_estimate=source.coverage_estimate,
            directional_analysis=source.directional_analysis,
            calibration_set=source.calibration_set,
            supersedes=source,
            actor=request.user,
        )
        record_event(
            actor=request.user,
            action="phase2_validation.retried",
            target=bundle,
            details={
                "supersedes_id": str(source.id),
                "input_sha256": bundle.input_sha256,
            },
        )
        return Response(
            Phase2ValidationBundleSerializer(bundle).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(request=None, responses={200: Phase2ValidationBundleSerializer})
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        bundle = approve_validation_bundle(self.get_object(), actor=request.user)
        record_event(
            actor=request.user,
            action="phase2_validation.approved",
            target=bundle,
            details={
                "changed_fields": ["approved_at", "approved_by", "status"],
                "result_sha256": bundle.result_sha256,
                "validation_profile_version": bundle.validation_profile_version,
            },
        )
        return Response(Phase2ValidationBundleSerializer(bundle).data)

    def _require_controlled_export_permission(self, request, bundle):
        if not user_has_permission(request.user, PLAN_EXPORT, bundle.incident):
            raise PermissionDenied(
                "Controlled Phase 2 evidence export also requires plan export permission."
            )

    @extend_schema(request=None, responses={(200, "application/json"): OpenApiTypes.BINARY})
    @action(detail=True, methods=["get"])
    def export(self, request, pk=None):
        bundle = self.get_object()
        self._require_controlled_export_permission(request, bundle)
        content = validation_export_bytes(bundle)
        digest = sha256_bytes(content)
        record_event(
            actor=request.user,
            action="phase2_validation.exported",
            target=bundle,
            details={
                "format": "json",
                "content_sha256": digest,
                "byte_size": len(content),
                "result_sha256": bundle.result_sha256,
                "validation_profile_version": bundle.validation_profile_version,
            },
        )
        response = HttpResponse(content, content_type="application/json")
        response["Content-Disposition"] = (
            f'attachment; filename="phase-2-validation-{bundle.id}.json"'
        )
        response["X-Content-SHA256"] = digest
        return response

    @extend_schema(
        request=ExportDigestVerificationRequestSerializer,
        responses={200: OpenApiTypes.OBJECT},
    )
    @action(
        detail=True,
        methods=["post"],
        parser_classes=[JSONParser, MultiPartParser],
    )
    def verify(self, request, pk=None):
        bundle = self.get_object()
        self._require_controlled_export_permission(request, bundle)
        serializer = ExportDigestVerificationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        content_sha256 = serializer.validated_data.get("content_sha256")
        uploaded_file = serializer.validated_data.get("file")
        if uploaded_file is not None:
            if uploaded_file.size > 10 * 1024 * 1024:
                raise ValidationError({"file": "The verification upload limit is 10 MiB."})
            hasher = hashlib.sha256()
            for chunk in uploaded_file.chunks():
                hasher.update(chunk)
            content_sha256 = hasher.hexdigest()
        if not content_sha256:
            raise ValidationError({"content_sha256": "Provide a SHA-256 digest or a file to hash."})
        event = (
            AuditEvent.objects.filter(
                action="phase2_validation.exported",
                target_type=bundle._meta.label_lower,
                target_id=str(bundle.id),
                details__content_sha256=content_sha256.strip().lower(),
            )
            .order_by("sequence")
            .first()
        )
        record_event(
            actor=request.user,
            action="phase2_validation.export_verified",
            target=bundle,
            details={
                "content_sha256": content_sha256.strip().lower(),
                "verified": event is not None,
            },
        )
        if event is None:
            return Response(
                {
                    "verified": False,
                    "detail": "No controlled export audit event matches this digest.",
                }
            )
        return Response(
            {
                "verified": True,
                "audit_event_id": str(event.id),
                "occurred_at": event.occurred_at,
                "actor_id": event.actor_id,
                "byte_size": event.details.get("byte_size"),
                "result_sha256": event.details.get("result_sha256"),
            }
        )


class Phase2ValidationStatusView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        return Response(validation_status())


class TerrainAnalysisViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = TerrainAnalysis.objects.none()
    serializer_class = TerrainAnalysisSerializer
    permission_classes = [PolicyPermission]
    pagination_class = TerrainAnalysisPagination
    policy_actions = {
        "list": RF_VIEW,
        "retrieve": RF_VIEW,
        "create": RF_EDIT,
        "run": RF_EDIT,
        "cancel": RF_EDIT,
        "retry": RF_EDIT,
        "approve": RF_APPROVE,
    }

    def get_queryset(self):
        queryset = scoped_to_incidents(
            TerrainAnalysis.objects.select_related(
                "incident",
                "site",
                "coverage_estimate__haat_calculation",
                "created_by",
                "approved_by",
                "supersedes",
            ),
            self.request.user,
        )
        incident_id = self.request.query_params.get("incident")
        return queryset.filter(incident_id=incident_id) if incident_id else queryset

    def get_serializer_class(self):
        if self.action == "create":
            return CreateTerrainAnalysisSerializer
        return TerrainAnalysisSerializer

    @extend_schema(
        request=CreateTerrainAnalysisSerializer,
        responses={201: TerrainAnalysisSerializer},
    )
    def create(self, request, *args, **kwargs):
        request_serializer = CreateTerrainAnalysisSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        values = request_serializer.validated_data
        incident = values["coverage_estimate"].incident
        if not user_has_permission(request.user, RF_EDIT, incident):
            raise PermissionDenied("Your incident role cannot queue terrain analysis.")
        analysis = queue_terrain_analysis(actor=request.user, **values)
        record_event(
            actor=request.user,
            action="terrain_analysis.queued",
            target=analysis,
            details={
                "coverage_estimate_id": str(analysis.coverage_estimate_id),
                "provider": analysis.provider,
                "provider_version": analysis.provider_version,
                "dataset_version": analysis.dataset_version,
                "engine": analysis.engine,
                "engine_version": analysis.engine_version,
                "input_sha256": analysis.input_sha256,
            },
        )
        return Response(
            TerrainAnalysisSerializer(analysis).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(request=None, responses={200: TerrainAnalysisSerializer})
    @action(detail=True, methods=["post"])
    def run(self, request, pk=None):
        analysis = run_terrain_analysis(self.get_object())
        record_event(
            actor=request.user,
            action=(
                "terrain_analysis.completed"
                if analysis.job_state == TerrainAnalysis.JobState.COMPLETE
                else "terrain_analysis.failed"
            ),
            target=analysis,
            details={
                "job_state": analysis.job_state,
                "analysis_state": analysis.analysis_state,
                "failure_code": analysis.failure_code,
                "input_sha256": analysis.input_sha256,
                "result_sha256": analysis.result_sha256,
                "engine_version": analysis.engine_version,
            },
        )
        return Response(TerrainAnalysisSerializer(analysis).data)

    @extend_schema(request=None, responses={200: TerrainAnalysisSerializer})
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        analysis = cancel_terrain_analysis(self.get_object())
        record_event(
            actor=request.user,
            action="terrain_analysis.cancelled",
            target=analysis,
            details={
                "job_state": analysis.job_state,
                "failure_code": analysis.failure_code,
            },
        )
        return Response(TerrainAnalysisSerializer(analysis).data)

    @extend_schema(request=None, responses={201: TerrainAnalysisSerializer})
    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        source = self.get_object()
        analysis = queue_terrain_analysis(
            coverage_estimate=source.coverage_estimate,
            azimuth_deg=source.azimuth_deg,
            maximum_distance_m=source.maximum_distance_m,
            sample_interval_m=source.sample_interval_m,
            receiver_height_m=source.receiver_height_m,
            clearance_m=source.clearance_m,
            supersedes=source,
            actor=request.user,
        )
        record_event(
            actor=request.user,
            action="terrain_analysis.retried",
            target=analysis,
            details={
                "supersedes_id": str(source.id),
                "input_sha256": analysis.input_sha256,
            },
        )
        return Response(
            TerrainAnalysisSerializer(analysis).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(request=None, responses={200: TerrainAnalysisSerializer})
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        analysis = approve_terrain_analysis(self.get_object(), actor=request.user)
        record_event(
            actor=request.user,
            action="terrain_analysis.approved",
            target=analysis,
            details={
                "changed_fields": ["approved_at", "approved_by", "status"],
                "result_sha256": analysis.result_sha256,
                "engine_version": analysis.engine_version,
            },
        )
        return Response(TerrainAnalysisSerializer(analysis).data)


class TerrainAnalysisStatusView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: TerrainAnalysisStatusSerializer})
    def get(self, request):
        return Response(terrain_status())
