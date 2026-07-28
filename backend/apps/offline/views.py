from django.db.models import QuerySet
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.accounts.policy import role_for_user
from apps.audit.services import record_event

from .models import OfflinePackage
from .serializers import (
    CreateOfflinePackageSerializer,
    OfflineConflictResolutionSerializer,
    OfflinePackageSerializer,
    OfflinePackageSummarySerializer,
    ResolveOfflineConflictSerializer,
    SynchronizeOfflinePackageSerializer,
)
from .services import (
    create_package,
    offline_status,
    package_current_status,
    resolve_conflict,
    support_bundle,
    synchronize_package,
)


class OfflineStatusView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: dict})
    def get(self, request):
        return Response(offline_status())


class OfflinePackageViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = OfflinePackage.objects.none()
    serializer_class = OfflinePackageSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self) -> QuerySet:
        queryset = OfflinePackage.objects.select_related(
            "incident",
            "requested_by",
        ).prefetch_related(
            "mutation_receipts__resolution",
        )
        if role_for_user(self.request.user) != Role.ADMINISTRATOR:
            queryset = queryset.filter(
                requested_by=self.request.user,
            )
        incident_id = self.request.query_params.get("incident")
        return queryset.filter(incident_id=incident_id) if incident_id else queryset

    def get_serializer_class(self):
        if self.action == "create":
            return CreateOfflinePackageSerializer
        if self.action == "list":
            return OfflinePackageSummarySerializer
        return OfflinePackageSerializer

    @extend_schema(
        request=CreateOfflinePackageSerializer,
        responses={201: OfflinePackageSerializer},
    )
    def create(self, request, *args, **kwargs):
        serializer = CreateOfflinePackageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        package = create_package(
            actor=request.user,
            incident_id=values["incident"],
            device_id=values["device_id"],
            expires_in_hours=values["expires_in_hours"],
            selection=values["selection"],
        )
        return Response(
            OfflinePackageSerializer(package, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def _require_owner(self, package: OfflinePackage):
        if package.requested_by_id != self.request.user.pk:
            raise PermissionDenied("Only the user who created this package may control it.")

    @extend_schema(
        request=SynchronizeOfflinePackageSerializer,
        responses={200: dict},
    )
    @action(detail=True, methods=["post"])
    def synchronize(self, request, pk=None):
        package = self.get_object()
        self._require_owner(package)
        serializer = SynchronizeOfflinePackageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            synchronize_package(
                package=package,
                actor=request.user,
                **serializer.validated_data,
            )
        )

    @extend_schema(request=None, responses={200: OfflinePackageSerializer})
    @action(detail=True, methods=["post"])
    def lock(self, request, pk=None):
        package = self.get_object()
        self._require_owner(package)
        current_status = package_current_status(package, request.user)
        if current_status != OfflinePackage.Status.ACTIVE:
            raise ValidationError(f"Only an active package can be locked; it is {current_status}.")
        package.status = OfflinePackage.Status.LOCKED
        package.locked_at = timezone.now()
        package.save(update_fields=["status", "locked_at", "updated_at"])
        record_event(
            actor=request.user,
            action="offline_package.locked",
            target=package,
            details={"manifest_sha256": package.manifest_sha256},
        )
        return Response(OfflinePackageSerializer(package, context={"request": request}).data)

    @extend_schema(request=None, responses={200: OfflinePackageSerializer})
    @action(detail=True, methods=["post"])
    def unlock(self, request, pk=None):
        package = self.get_object()
        self._require_owner(package)
        current_status = package_current_status(package, request.user)
        if current_status != OfflinePackage.Status.LOCKED:
            raise ValidationError(f"Only a locked package can be unlocked; it is {current_status}.")
        package.status = OfflinePackage.Status.ACTIVE
        package.locked_at = None
        package.save(update_fields=["status", "locked_at", "updated_at"])
        record_event(
            actor=request.user,
            action="offline_package.unlocked",
            target=package,
            details={"manifest_sha256": package.manifest_sha256},
        )
        return Response(OfflinePackageSerializer(package, context={"request": request}).data)

    @extend_schema(request=None, responses={200: OfflinePackageSerializer})
    @action(detail=True, methods=["post"])
    def purge(self, request, pk=None):
        package = self.get_object()
        self._require_owner(package)
        if package.status == OfflinePackage.Status.PURGED:
            raise ValidationError("This package was already purged.")
        package.status = OfflinePackage.Status.PURGED
        package.payload_snapshot = {}
        package.revision_state = {}
        package.purged_at = timezone.now()
        package.save(
            update_fields=[
                "status",
                "payload_snapshot",
                "revision_state",
                "purged_at",
                "updated_at",
            ]
        )
        record_event(
            actor=request.user,
            action="offline_package.purged",
            target=package,
            details={
                "manifest_sha256": package.manifest_sha256,
                "receipt_count": package.mutation_receipts.count(),
            },
        )
        return Response(OfflinePackageSerializer(package, context={"request": request}).data)

    @extend_schema(
        request=ResolveOfflineConflictSerializer,
        responses={201: OfflineConflictResolutionSerializer},
    )
    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        package = self.get_object()
        self._require_owner(package)
        serializer = ResolveOfflineConflictSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        resolution = resolve_conflict(
            package=package,
            actor=request.user,
            **serializer.validated_data,
        )
        return Response(
            OfflineConflictResolutionSerializer(resolution).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(request=None, responses={200: dict})
    @action(detail=True, methods=["get"])
    def support(self, request, pk=None):
        package = self.get_object()
        self._require_owner(package)
        bundle = support_bundle(package)
        record_event(
            actor=request.user,
            action="offline_package.support_bundle_exported",
            target=package,
            details={
                "manifest_sha256": package.manifest_sha256,
                "receipt_count": len(bundle["receipt_summary"]),
            },
        )
        return Response(bundle)
