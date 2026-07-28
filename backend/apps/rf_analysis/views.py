from django.db.models import Prefetch
from django.utils import timezone
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

from .elevation import provider_status
from .haat import (
    approve_haat_calculation,
    create_haat_calculation,
    retry_haat_calculation,
)
from .models import (
    ElevationSnapshot,
    HAATCalculation,
    RFAnalysisInputSnapshot,
    SubscriberProfile,
    SubscriberProfileVersion,
)
from .serializers import (
    CreateHAATCalculationSerializer,
    CreateRFAnalysisInputSnapshotSerializer,
    ElevationSnapshotSerializer,
    HAATCalculationSerializer,
    RFAnalysisInputSnapshotSerializer,
    SubscriberProfileSerializer,
    SubscriberProfileVersionSerializer,
)
from .services import (
    VERSION_EDITABLE_FIELDS,
    approve_version,
    archive_analysis_snapshot,
    copy_version,
    create_analysis_snapshot,
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
