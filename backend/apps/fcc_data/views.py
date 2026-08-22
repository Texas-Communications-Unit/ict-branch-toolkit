from decimal import Decimal, InvalidOperation

from django.db.models import Count, Q
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from apps.accounts.permissions import PolicyPermission
from apps.accounts.policy import LIBRARY_VIEW

from .models import AntennaStructure, UlsEmission, UlsFrequency, UlsLicense, UlsLocation
from .serializers import (
    AntennaStructureSerializer,
    FccTowerDetailSerializer,
    UlsLicenseSerializer,
)


class FccSearchPagination(PageNumberPagination):
    page_size = 50
    max_page_size = 1000
    page_size_query_param = "page_size"


class FccReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [PolicyPermission]
    policy_actions = {"list": LIBRARY_VIEW, "retrieve": LIBRARY_VIEW}
    pagination_class = FccSearchPagination


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter(name=name, type=float, required=False, description=description)
            for name, description in (
                ("west", "Western WGS 84 longitude; requires all four map bounds."),
                ("south", "Southern WGS 84 latitude; requires all four map bounds."),
                ("east", "Eastern WGS 84 longitude; requires all four map bounds."),
                ("north", "Northern WGS 84 latitude; requires all four map bounds."),
            )
        ]
    )
)
class AntennaStructureViewSet(FccReadOnlyViewSet):
    serializer_class = AntennaStructureSerializer

    def get_queryset(self):
        queryset = AntennaStructure.objects.select_related("batch").filter(batch__is_current=True)
        search = self.request.query_params.get("search", "").strip()
        status_code = self.request.query_params.get("status", "").strip()
        if search:
            queryset = queryset.filter(
                Q(registration_number__icontains=search)
                | Q(owner_name__icontains=search)
                | Q(owner_frn__icontains=search)
                | Q(faa_study_number__icontains=search)
                | Q(structure_type__icontains=search)
            )
        if status_code:
            queryset = queryset.filter(status_code__iexact=status_code)
        bounds = [
            self.request.query_params.get(name) for name in ("west", "south", "east", "north")
        ]
        if any(value is not None for value in bounds):
            if not all(value not in {None, ""} for value in bounds):
                raise ValidationError("west, south, east, and north are required together.")
            try:
                west, south, east, north = (Decimal(value) for value in bounds)
            except (InvalidOperation, TypeError) as error:
                raise ValidationError("Map bounds must be decimal coordinates.") from error
            if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
                raise ValidationError("Map bounds are outside WGS 84 limits or are reversed.")
            queryset = queryset.filter(
                latitude__isnull=False,
                longitude__isnull=False,
                longitude__gte=west,
                longitude__lte=east,
                latitude__gte=south,
                latitude__lte=north,
            )
        return queryset

    @extend_schema(responses=FccTowerDetailSerializer)
    @action(detail=True, methods=["get"], url_path="tower-details")
    def tower_details(self, request, pk=None):
        structure = self.get_object()
        matching_locations = UlsLocation.objects.filter(
            license__batch__is_current=True,
            asr_registration_number=structure.registration_number,
        ).order_by("location_number")
        license_queryset = (
            UlsLicense.objects.select_related("batch")
            .filter(
                batch__is_current=True,
                locations__asr_registration_number=structure.registration_number,
            )
            .distinct()
            .order_by("call_sign", "unique_system_identifier")
        )
        license_count = license_queryset.count()
        licenses = list(license_queryset[:100])
        for license_record in licenses:
            locations = list(matching_locations.filter(license=license_record))
            for location in locations:
                location.frequencies = list(
                    UlsFrequency.objects.filter(
                        license=license_record, location_number=location.location_number
                    ).order_by("frequency_hz", "antenna_number")
                )
                location.emissions = list(
                    UlsEmission.objects.filter(
                        license=license_record, location_number=location.location_number
                    ).order_by("frequency_hz", "antenna_number", "emission_designator")
                )
            license_record.tower_locations = locations
        payload = {
            "structure": structure,
            "licenses": licenses,
            "license_count": license_count,
            "truncated": license_count > len(licenses),
            "disclaimer": (
                "FCC reference data is planning decision support and does not authorize "
                "frequency use, transmission, coordination, or site access."
            ),
        }
        return Response(FccTowerDetailSerializer(payload).data)


class UlsLicenseViewSet(FccReadOnlyViewSet):
    serializer_class = UlsLicenseSerializer

    def get_queryset(self):
        queryset = (
            UlsLicense.objects.select_related("batch")
            .filter(batch__is_current=True)
            .annotate(
                location_count=Count("locations", distinct=True),
                frequency_count=Count("frequencies", distinct=True),
            )
        )
        search = self.request.query_params.get("search", "").strip()
        state = self.request.query_params.get("state", "").strip()
        service = self.request.query_params.get("service_code", "").strip()
        status_code = self.request.query_params.get("status", "").strip()
        if search:
            queryset = queryset.filter(
                Q(call_sign__icontains=search)
                | Q(licensee_name__icontains=search)
                | Q(frn__icontains=search)
                | Q(city__icontains=search)
            )
        if state:
            queryset = queryset.filter(state__iexact=state)
        if service:
            queryset = queryset.filter(radio_service_code__iexact=service)
        if status_code:
            queryset = queryset.filter(license_status__iexact=status_code)
        return queryset
