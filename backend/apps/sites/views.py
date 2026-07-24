from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db.models import QuerySet
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.exceptions import MethodNotAllowed, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.accounts.permissions import PolicyPermission
from apps.accounts.policy import (
    SITE_EDIT,
    SITE_EXPORT,
    SITE_VIEW,
    role_for_user,
    user_has_permission,
)
from apps.audit.services import record_event, record_export
from apps.plans.models import PlanRevision

from .coordinates import CoordinateError, coordinate_formats, parse_coordinate
from .exports import EXPORTERS
from .geocoders import configured_geocoder
from .models import ManualRing, RadioSite, SiteAssignment
from .serializers import (
    CoordinateParseSerializer,
    GeocoderQuerySerializer,
    ManualRingSerializer,
    RadioSiteSerializer,
    SiteAssignmentSerializer,
)


def scoped_sites(queryset: QuerySet, user, incident_path="incident"):
    if role_for_user(user) == Role.ADMINISTRATOR:
        return queryset
    return queryset.filter(
        **{
            f"{incident_path}__memberships__user": user,
            f"{incident_path}__memberships__is_active": True,
        }
    ).distinct()


class RadioSiteViewSet(viewsets.ModelViewSet):
    queryset = RadioSite.objects.none()
    serializer_class = RadioSiteSerializer
    permission_classes = [PolicyPermission]
    policy_actions = {
        "list": SITE_VIEW,
        "retrieve": SITE_VIEW,
        "create": SITE_EDIT,
        "update": SITE_EDIT,
        "partial_update": SITE_EDIT,
    }

    def get_queryset(self):
        queryset = scoped_sites(
            RadioSite.objects.filter(archived_at__isnull=True).prefetch_related("rings"),
            self.request.user,
        )
        incident = self.request.query_params.get("incident")
        if incident:
            queryset = queryset.filter(incident_id=incident)
        bbox = self.request.query_params.get("bbox")
        if bbox:
            try:
                west, south, east, north = [Decimal(item) for item in bbox.split(",")]
            except (InvalidOperation, ValueError) as exc:
                raise ValidationError({"bbox": "Use west,south,east,north."}) from exc
            if not (-180 <= west <= east <= 180 and -90 <= south <= north <= 90):
                raise ValidationError({"bbox": "Bounding coordinates are invalid."})
            if settings.ENABLE_GIS:
                from django.contrib.gis.geos import Polygon

                queryset = queryset.filter(
                    location__within=Polygon.from_bbox(
                        tuple(float(value) for value in (west, south, east, north))
                    )
                )
            else:
                queryset = queryset.filter(
                    longitude__gte=west,
                    longitude__lte=east,
                    latitude__gte=south,
                    latitude__lte=north,
                )
        return queryset

    def perform_create(self, serializer):
        incident = serializer.validated_data["incident"]
        if not user_has_permission(self.request.user, SITE_EDIT, incident):
            raise PermissionDenied("Your incident role cannot create sites.")
        site = serializer.save(created_by=self.request.user)
        record_event(actor=self.request.user, action="site.created", target=site)

    def perform_update(self, serializer):
        site = serializer.save()
        record_event(
            actor=self.request.user,
            action="site.updated",
            target=site,
            details={"changed_fields": sorted(serializer.validated_data)},
        )

    def destroy(self, request, *args, **kwargs):
        raise MethodNotAllowed("DELETE", detail="Archive sites through a later retention workflow.")


class ManualRingViewSet(viewsets.ModelViewSet):
    queryset = ManualRing.objects.none()
    serializer_class = ManualRingSerializer
    permission_classes = [PolicyPermission]
    policy_actions = {
        "list": SITE_VIEW,
        "retrieve": SITE_VIEW,
        "create": SITE_EDIT,
        "update": SITE_EDIT,
        "partial_update": SITE_EDIT,
        "destroy": SITE_EDIT,
    }

    def get_queryset(self):
        queryset = scoped_sites(
            ManualRing.objects.select_related("site__incident"),
            self.request.user,
            "site__incident",
        )
        site = self.request.query_params.get("site")
        return queryset.filter(site_id=site) if site else queryset

    def perform_create(self, serializer):
        site = serializer.validated_data["site"]
        if not user_has_permission(self.request.user, SITE_EDIT, site.incident):
            raise PermissionDenied("Your incident role cannot create rings.")
        ring = serializer.save()
        record_event(actor=self.request.user, action="site_ring.created", target=ring)

    def perform_update(self, serializer):
        ring = serializer.save()
        record_event(actor=self.request.user, action="site_ring.updated", target=ring)

    def perform_destroy(self, instance):
        record_event(actor=self.request.user, action="site_ring.deleted", target=instance)
        instance.delete()


class SiteAssignmentViewSet(viewsets.ModelViewSet):
    queryset = SiteAssignment.objects.none()
    serializer_class = SiteAssignmentSerializer
    permission_classes = [PolicyPermission]
    policy_actions = {
        "list": SITE_VIEW,
        "retrieve": SITE_VIEW,
        "create": SITE_EDIT,
        "destroy": SITE_EDIT,
    }

    def get_queryset(self):
        queryset = scoped_sites(
            SiteAssignment.objects.select_related(
                "site__incident", "assignment__revision__plan__incident"
            ),
            self.request.user,
            "site__incident",
        )
        revision = self.request.query_params.get("revision")
        return queryset.filter(assignment__revision_id=revision) if revision else queryset

    def perform_create(self, serializer):
        site = serializer.validated_data["site"]
        if not user_has_permission(self.request.user, SITE_EDIT, site.incident):
            raise PermissionDenied("Your incident role cannot associate sites.")
        link = serializer.save()
        record_event(actor=self.request.user, action="site_assignment.created", target=link)

    def update(self, request, *args, **kwargs):
        raise MethodNotAllowed("PUT", detail="Site links are replaced, not edited.")

    def partial_update(self, request, *args, **kwargs):
        raise MethodNotAllowed("PATCH", detail="Site links are replaced, not edited.")

    def perform_destroy(self, instance):
        if instance.assignment.revision.is_locked:
            raise ValidationError("Approved assignment site links are immutable.")
        record_event(actor=self.request.user, action="site_assignment.deleted", target=instance)
        instance.delete()


class CoordinateParseView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=CoordinateParseSerializer,
        responses={200: OpenApiTypes.OBJECT},
    )
    def post(self, request):
        serializer = CoordinateParseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            parsed = parse_coordinate(serializer.validated_data["coordinate"])
        except CoordinateError as exc:
            raise ValidationError({"coordinate": str(exc)}) from exc
        return Response(
            {
                "latitude": round(parsed.latitude, 6),
                "longitude": round(parsed.longitude, 6),
                "input_format": parsed.input_format,
                "formats": coordinate_formats(parsed.latitude, parsed.longitude),
            }
        )


class GeocoderSearchView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=GeocoderQuerySerializer,
        responses={200: OpenApiTypes.OBJECT},
    )
    def post(self, request):
        serializer = GeocoderQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        provider = configured_geocoder()
        results = provider.search(serializer.validated_data["address"])
        return Response(
            {
                "provider": provider.name,
                "configured": provider.name != "disabled",
                "results": [
                    {
                        "label": item.label,
                        "latitude": item.latitude,
                        "longitude": item.longitude,
                        "provider": item.provider,
                    }
                    for item in results
                ],
            }
        )


class SpatialExportView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: OpenApiTypes.BINARY})
    def get(self, request, revision_id, export_format):
        revision = get_object_or_404(
            PlanRevision.objects.select_related("plan__incident"), pk=revision_id
        )
        if not user_has_permission(request.user, SITE_EXPORT, revision.plan.incident):
            raise PermissionDenied("Your incident role cannot export approved site data.")
        try:
            content_type, filename, exporter = EXPORTERS[export_format]
        except KeyError as exc:
            raise ValidationError({"format": "Choose map, kml, geojson, or csv."}) from exc
        payload = exporter(revision)
        record_export(
            actor=request.user,
            action=f"site_export.{export_format}",
            revision=revision,
            export_format=export_format,
            content=payload,
            details={"filename": filename},
        )
        response = HttpResponse(payload, content_type=content_type, status=status.HTTP_200_OK)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
