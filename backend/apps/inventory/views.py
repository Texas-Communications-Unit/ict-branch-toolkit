from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import Role
from apps.accounts.policy import (
    INVENTORY_MANAGE,
    INVENTORY_VIEW,
    role_for_user,
    user_has_permission,
)
from apps.audit.services import record_event
from apps.incidents.models import Incident

from .models import Asset, AssetCheckout, ChargingRecord, MaintenanceRecord, ProgrammingRecord
from .serializers import (
    AccountabilityHoldResolutionSerializer,
    AssetCheckoutCreateSerializer,
    AssetCheckoutSerializer,
    AssetReturnSerializer,
    AssetSerializer,
    ChargingRecordSerializer,
    MaintenanceRecordSerializer,
    ProgrammingRecordSerializer,
)
from .services import (
    checkout_assets,
    record_charging,
    record_maintenance,
    record_programming,
    resolve_accountability_hold,
    return_asset,
)


def _can_access_incident(user, incident):
    return user_has_permission(user, INVENTORY_VIEW, incident)


class AssetViewSet(viewsets.ModelViewSet):
    queryset = Asset.objects.select_related("parent", "created_by")
    serializer_class = AssetSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = []

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(asset_id__icontains=search)
                | Q(serial_number__icontains=search)
                | Q(alias__icontains=search)
                | Q(manufacturer__icontains=search)
                | Q(model__icontains=search)
            )
        category = self.request.query_params.get("category", "").strip()
        asset_status = self.request.query_params.get("status", "").strip()
        if category:
            queryset = queryset.filter(category=category)
        if asset_status:
            queryset = queryset.filter(status=asset_status)
        ordering = self.request.query_params.get("ordering", "asset_id")
        if ordering.lstrip("-") in {"asset_id", "category", "status", "manufacturer", "model"}:
            queryset = queryset.order_by(ordering)
        return queryset

    def _require(self, permission):
        if not user_has_permission(self.request.user, permission):
            raise PermissionDenied("Your role cannot perform this inventory action.")

    def list(self, request, *args, **kwargs):
        self._require(INVENTORY_VIEW)
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        self._require(INVENTORY_VIEW)
        return super().retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        self._require(INVENTORY_MANAGE)
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        self._require(INVENTORY_MANAGE)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        self._require(INVENTORY_MANAGE)
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        raise PermissionDenied("Inventory records are retired, not deleted.")

    def perform_create(self, serializer):
        asset = serializer.save(created_by=self.request.user)
        record_event(
            actor=self.request.user,
            action="inventory.asset_created",
            target=asset,
            details={"asset_id": asset.asset_id, "category": asset.category},
        )

    def perform_update(self, serializer):
        asset = serializer.save()
        record_event(
            actor=self.request.user,
            action="inventory.asset_updated",
            target=asset,
            details={"asset_id": asset.asset_id, "category": asset.category},
        )


class AssetCheckoutViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AssetCheckout.objects.select_related(
        "incident",
        "asset",
        "asset__created_by",
        "checked_out_by",
        "returned_by",
        "hold_resolved_by",
    )
    serializer_class = AssetCheckoutSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        if role_for_user(self.request.user) != Role.ADMINISTRATOR:
            queryset = queryset.filter(
                incident__memberships__user=self.request.user,
                incident__memberships__is_active=True,
            ).distinct()
        incident = self.request.query_params.get("incident")
        return queryset.filter(incident_id=incident) if incident else queryset

    def list(self, request, *args, **kwargs):
        if not user_has_permission(request.user, INVENTORY_VIEW):
            raise PermissionDenied("Your role cannot view inventory checkouts.")
        incident_id = request.query_params.get("incident")
        if not incident_id:
            raise PermissionDenied("Select an incident before viewing accountable checkouts.")
        incident = get_object_or_404(Incident, pk=incident_id)
        if not _can_access_incident(request.user, incident):
            raise PermissionDenied("You do not have access to this incident.")
        response = super().list(request, *args, **kwargs)
        record_count = (
            response.data.get("count", 0) if isinstance(response.data, dict) else len(response.data)
        )
        record_event(
            actor=request.user,
            action="inventory.driver_license_records_viewed",
            target=incident,
            details={"record_count": record_count},
        )
        return response

    def retrieve(self, request, *args, **kwargs):
        checkout = self.get_object()
        if not _can_access_incident(request.user, checkout.incident):
            raise PermissionDenied("You do not have access to this incident.")
        record_event(
            actor=request.user,
            action="inventory.driver_license_record_viewed",
            target=checkout,
            details={
                "incident_id": str(checkout.incident_id),
                "asset_id": checkout.asset.asset_id,
            },
        )
        return Response(self.get_serializer(checkout).data)

    @extend_schema(
        request=AssetCheckoutCreateSerializer,
        responses={201: AssetCheckoutSerializer(many=True)},
    )
    def create(self, request, *args, **kwargs):
        serializer = AssetCheckoutCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        incident = get_object_or_404(Incident, pk=serializer.validated_data["incident"])
        if not user_has_permission(request.user, INVENTORY_MANAGE, incident):
            raise PermissionDenied("Your incident role cannot check out radios.")
        assets = list(Asset.objects.filter(pk__in=serializer.validated_data["assets"]))
        if len(assets) != len(serializer.validated_data["assets"]):
            return Response({"assets": ["One or more assets do not exist."]}, status=400)
        checkouts = checkout_assets(
            assets=assets,
            incident=incident,
            assigned_name=serializer.validated_data["assigned_name"],
            assigned_organization=serializer.validated_data["assigned_organization"],
            jurisdiction=serializer.validated_data["driver_license_jurisdiction"],
            number=serializer.validated_data["driver_license_number"],
            actor=request.user,
            point_of_contact=serializer.validated_data.get("point_of_contact", ""),
            phone_number=serializer.validated_data.get("phone_number", ""),
            mailing_address=serializer.validated_data.get("mailing_address", ""),
            assignment_notes=serializer.validated_data.get("assignment_notes", ""),
        )
        return Response(
            AssetCheckoutSerializer(checkouts, many=True).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(request=AssetReturnSerializer, responses=AssetCheckoutSerializer)
    @action(detail=True, methods=["post"], url_path="return")
    def record_return(self, request, pk=None):
        checkout = self.get_object()
        if not user_has_permission(request.user, INVENTORY_MANAGE, checkout.incident):
            raise PermissionDenied("Your incident role cannot return radios.")
        serializer = AssetReturnSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        checkout = return_asset(
            checkout=checkout,
            condition=serializer.validated_data["condition"],
            hold_reason=serializer.validated_data.get("hold_reason", ""),
            actor=request.user,
        )
        return Response(AssetCheckoutSerializer(checkout).data)

    @extend_schema(
        request=AccountabilityHoldResolutionSerializer,
        responses=AssetCheckoutSerializer,
    )
    @action(detail=True, methods=["post"], url_path="resolve-hold")
    def resolve_hold(self, request, pk=None):
        checkout = self.get_object()
        if not user_has_permission(request.user, INVENTORY_MANAGE, checkout.incident):
            raise PermissionDenied("Your incident role cannot resolve accountability holds.")
        serializer = AccountabilityHoldResolutionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        checkout = resolve_accountability_hold(
            checkout=checkout,
            asset_status=serializer.validated_data["asset_status"],
            resolution_note=serializer.validated_data["resolution_note"],
            actor=request.user,
        )
        return Response(AssetCheckoutSerializer(checkout).data)


class ProgrammingRecordViewSet(viewsets.ModelViewSet):
    queryset = ProgrammingRecord.objects.select_related("asset", "confirmed_by")
    serializer_class = ProgrammingRecordSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def list(self, request, *args, **kwargs):
        if not user_has_permission(request.user, INVENTORY_VIEW):
            raise PermissionDenied("Your role cannot view programming records.")
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        if not user_has_permission(request.user, INVENTORY_MANAGE):
            raise PermissionDenied("Your role cannot record programming work.")
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.instance = record_programming(
            actor=self.request.user, **serializer.validated_data
        )


class InventoryRecordViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def _require(self, permission):
        if not user_has_permission(self.request.user, permission):
            raise PermissionDenied("Your role cannot perform this inventory action.")

    def list(self, request, *args, **kwargs):
        self._require(INVENTORY_VIEW)
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        self._require(INVENTORY_VIEW)
        return super().retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        self._require(INVENTORY_MANAGE)
        return super().create(request, *args, **kwargs)


class MaintenanceRecordViewSet(InventoryRecordViewSet):
    queryset = MaintenanceRecord.objects.select_related("asset", "recorded_by")
    serializer_class = MaintenanceRecordSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        asset = self.request.query_params.get("asset")
        return queryset.filter(asset_id=asset) if asset else queryset

    def perform_create(self, serializer):
        serializer.instance = record_maintenance(
            actor=self.request.user, **serializer.validated_data
        )


class ChargingRecordViewSet(InventoryRecordViewSet):
    queryset = ChargingRecord.objects.select_related("asset", "recorded_by")
    serializer_class = ChargingRecordSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        asset = self.request.query_params.get("asset")
        return queryset.filter(asset_id=asset) if asset else queryset

    def perform_create(self, serializer):
        serializer.instance = record_charging(actor=self.request.user, **serializer.validated_data)
