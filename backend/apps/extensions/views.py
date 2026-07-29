import hashlib

from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.accounts.permissions import PolicyPermission
from apps.accounts.policy import (
    EXTENSION_ADMIN,
    EXTENSION_RUN,
    EXTENSION_VIEW,
    role_for_user,
    user_has_permission,
)
from apps.audit.services import record_event

from .models import ExtensionExecution
from .serializers import (
    CreateExtensionExecutionSerializer,
    ExtensionCatalogEntrySerializer,
    ExtensionExecutionSerializer,
    ExtensionInstallationSerializer,
    ExtensionInstallRequestSerializer,
)
from .services import (
    build_execution_package,
    execute_extension,
    extension_catalog,
    install_extension,
    set_extension_enabled,
)


class AdministratorOnly(BasePermission):
    def has_permission(self, request, view):
        return user_has_permission(request.user, EXTENSION_ADMIN)


class ExtensionCatalogView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: ExtensionCatalogEntrySerializer(many=True)})
    def get(self, request):
        if not user_has_permission(request.user, EXTENSION_VIEW):
            raise PermissionDenied("Your role cannot view the extension catalog.")
        return Response(extension_catalog())


class ExtensionInstallView(APIView):
    permission_classes = [AdministratorOnly]

    @extend_schema(
        request=ExtensionInstallRequestSerializer,
        responses={201: ExtensionInstallationSerializer},
    )
    def post(self, request):
        serializer = ExtensionInstallRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        installation = install_extension(actor=request.user, **serializer.validated_data)
        return Response(
            ExtensionInstallationSerializer(installation).data,
            status=status.HTTP_201_CREATED,
        )


class ExtensionEnableView(APIView):
    permission_classes = [AdministratorOnly]
    enabled = True

    @extend_schema(request=None, responses={200: ExtensionInstallationSerializer})
    def post(self, request, extension_key):
        installation = set_extension_enabled(
            extension_key=extension_key,
            enabled=self.enabled,
            actor=request.user,
        )
        return Response(ExtensionInstallationSerializer(installation).data)


class ExtensionDisableView(ExtensionEnableView):
    enabled = False


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter(
                name="incident",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description="Limit retained extension executions to one incident.",
            )
        ]
    ),
    create=extend_schema(
        request=CreateExtensionExecutionSerializer,
        responses={201: ExtensionExecutionSerializer},
    ),
)
class ExtensionExecutionViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = ExtensionExecution.objects.none()
    serializer_class = ExtensionExecutionSerializer
    permission_classes = [PolicyPermission]
    policy_actions = {
        "list": EXTENSION_VIEW,
        "retrieve": EXTENSION_VIEW,
        "create": EXTENSION_RUN,
        "export": EXTENSION_VIEW,
    }

    def get_queryset(self):
        queryset = ExtensionExecution.objects.select_related(
            "installation",
            "incident",
            "source_revision",
            "source_revision__plan",
            "created_by",
        )
        if role_for_user(self.request.user) != Role.ADMINISTRATOR:
            queryset = queryset.filter(
                incident__memberships__user=self.request.user,
                incident__memberships__is_active=True,
            ).distinct()
        incident_id = self.request.query_params.get("incident")
        return queryset.filter(incident_id=incident_id) if incident_id else queryset

    def create(self, request, *args, **kwargs):
        input_serializer = CreateExtensionExecutionSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        incident = input_serializer.validated_data["incident"]
        if not user_has_permission(request.user, EXTENSION_RUN, incident):
            raise PermissionDenied("Your incident role cannot run planning extensions.")
        execution = execute_extension(
            extension_key=input_serializer.validated_data["extension_key"],
            contract_version=input_serializer.validated_data["contract_version"],
            capability=input_serializer.validated_data["capability"],
            incident=incident,
            source_revision=input_serializer.validated_data["source_revision"],
            parameters=input_serializer.validated_data["inputs"],
            actor=request.user,
        )
        output_status = (
            status.HTTP_201_CREATED
            if execution.status == ExtensionExecution.Status.COMPLETE
            else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        return Response(self.get_serializer(execution).data, status=output_status)

    @extend_schema(responses={(200, "application/json"): OpenApiTypes.BINARY})
    @action(detail=True, methods=["get"])
    def export(self, request, pk=None):
        execution = self.get_object()
        if not user_has_permission(request.user, EXTENSION_VIEW, execution.incident):
            raise PermissionDenied("Your incident role cannot export extension output.")
        content = build_execution_package(execution)
        content_sha256 = hashlib.sha256(content).hexdigest()
        record_event(
            actor=request.user,
            action="extension.exported",
            target=execution,
            details={
                "extension_key": execution.extension_key,
                "extension_version": execution.extension_version,
                "capability": execution.capability,
                "incident_id": str(execution.incident_id),
                "source_revision_id": str(execution.source_revision_id),
                "content_sha256": content_sha256,
                "byte_size": len(content),
            },
        )
        response = HttpResponse(content, content_type="application/json")
        response["Content-Disposition"] = (
            f'attachment; filename="{execution.extension_key}-{execution.capability}.json"'
        )
        response["X-Content-SHA256"] = content_sha256
        response["X-Content-Type-Options"] = "nosniff"
        return response
