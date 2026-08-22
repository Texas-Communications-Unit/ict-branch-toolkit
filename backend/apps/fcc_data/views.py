from decimal import Decimal, InvalidOperation

from django.db.models import Avg, Count, F, Min, Q, Value
from django.db.models.functions import Floor
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
    FccMapFeatureCollectionSerializer,
    FccMapFeatureSerializer,
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
    policy_actions = {
        **FccReadOnlyViewSet.policy_actions,
        "map_features": LIBRARY_VIEW,
        "tower_details": LIBRARY_VIEW,
    }

    def _filtered_queryset(self):
        queryset = AntennaStructure.objects.select_related("batch").filter(batch__is_current=True)
        search = self.request.query_params.get("search", "").strip()
        status_code = self.request.query_params.get("status", "").strip()
        structure_type = self.request.query_params.get("structure_type", "").strip()
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
        if structure_type:
            queryset = queryset.filter(structure_type__iexact=structure_type)
        return queryset

    def _bounded_queryset(self):
        queryset = self._filtered_queryset()
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

    def get_queryset(self):
        return self._bounded_queryset()

    @extend_schema(
        parameters=[
            OpenApiParameter(name="west", type=float, required=True),
            OpenApiParameter(name="south", type=float, required=True),
            OpenApiParameter(name="east", type=float, required=True),
            OpenApiParameter(name="north", type=float, required=True),
            OpenApiParameter(name="zoom", type=float, required=True),
            OpenApiParameter(name="search", type=str, required=False),
            OpenApiParameter(name="status", type=str, required=False),
            OpenApiParameter(name="structure_type", type=str, required=False),
        ],
        responses=FccMapFeatureCollectionSerializer,
    )
    @action(detail=False, methods=["get"], url_path="map-features")
    def map_features(self, request):
        required_bounds = ("west", "south", "east", "north")
        if not all(request.query_params.get(name, "").strip() for name in required_bounds):
            raise ValidationError("west, south, east, and north are required.")
        try:
            zoom = float(request.query_params.get("zoom", ""))
        except (TypeError, ValueError) as error:
            raise ValidationError("zoom must be a number between 0 and 22.") from error
        if not 0 <= zoom <= 22:
            raise ValidationError("zoom must be a number between 0 and 22.")

        queryset = self._bounded_queryset()
        total_count = queryset.count()
        if zoom >= 16:
            towers = list(queryset.order_by("registration_number")[:2000])
            features = [
                {
                    "kind": "tower",
                    "key": str(tower.id),
                    "latitude": float(tower.latitude),
                    "longitude": float(tower.longitude),
                    "count": 1,
                    "tower": tower,
                }
                for tower in towers
            ]
        else:
            cell_size = Decimal(str(360 / (2 ** (zoom + 4))))
            groups = list(
                queryset.order_by()
                .annotate(
                    latitude_bucket=Floor(F("latitude") / Value(cell_size)),
                    longitude_bucket=Floor(F("longitude") / Value(cell_size)),
                )
                .values("latitude_bucket", "longitude_bucket")
                .annotate(
                    count=Count("id"),
                    latitude=Avg("latitude"),
                    longitude=Avg("longitude"),
                    registration_number=Min("registration_number"),
                )
                .order_by("latitude_bucket", "longitude_bucket")
            )
            single_registrations = [
                group["registration_number"] for group in groups if group["count"] == 1
            ]
            single_towers = {
                tower.registration_number: tower
                for tower in queryset.filter(registration_number__in=single_registrations)
            }
            features = []
            for group in groups:
                tower = single_towers.get(group["registration_number"])
                features.append(
                    {
                        "kind": "tower" if tower else "cluster",
                        "key": str(tower.id)
                        if tower
                        else f"{group['latitude_bucket']}:{group['longitude_bucket']}",
                        "latitude": float(group["latitude"]),
                        "longitude": float(group["longitude"]),
                        "count": group["count"],
                        "tower": tower,
                    }
                )
        return Response(
            {
                "count": total_count,
                "feature_count": len(features),
                "truncated": zoom >= 16 and total_count > len(features),
                "results": FccMapFeatureSerializer(features, many=True).data,
            }
        )

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
