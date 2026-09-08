from __future__ import annotations

from decimal import Decimal, InvalidOperation

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .elevation import (
    ElevationProviderError,
    configured_elevation_provider,
    source_is_approved,
)


class PointElevationView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(exclude=True)
    def get(self, request):
        try:
            latitude = Decimal(str(request.query_params["latitude"]))
            longitude = Decimal(str(request.query_params["longitude"]))
        except (KeyError, InvalidOperation, TypeError, ValueError):
            return Response(
                {"detail": "Valid latitude and longitude query parameters are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not latitude.is_finite() or latitude < -90 or latitude > 90:
            return Response(
                {"detail": "Latitude must be between -90 and 90 degrees."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not longitude.is_finite() or longitude < -180 or longitude > 180:
            return Response(
                {"detail": "Longitude must be between -180 and 180 degrees."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        provider = configured_elevation_provider()
        source = provider.source
        if not source_is_approved(source):
            return Response(
                {"detail": "An approved elevation source is not available."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            batch = provider.fetch(
                [
                    {
                        "role": "site",
                        "latitude": format(latitude, "f"),
                        "longitude": format(longitude, "f"),
                        "distance_m": "0",
                        "azimuth_deg": None,
                    }
                ]
            )
        except ElevationProviderError:
            return Response(
                {"detail": "The elevation service is temporarily unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if not batch.samples:
            return Response(
                {"detail": "The elevation service did not return a usable sample."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        sample = batch.samples[0]
        elevation_value = sample.get("transformed_elevation_m") or sample.get("elevation_m")
        if sample.get("state") != "complete" or elevation_value is None:
            return Response(
                {"detail": "Elevation is unavailable for this coordinate."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        elevation_m = Decimal(str(elevation_value))
        elevation_ft = elevation_m * Decimal("3.280839895013123")

        return Response(
            {
                "latitude": format(latitude, "f"),
                "longitude": format(longitude, "f"),
                "elevation_m": format(elevation_m.quantize(Decimal("0.1")), "f"),
                "elevation_ft": format(elevation_ft.quantize(Decimal("0.1")), "f"),
                "provider": source.provider,
                "dataset_product": source.dataset_product,
                "source_version": source.source_version,
                "vertical_crs": source.vertical_crs,
                "resolution_m": source.resolution_m,
                "source_resolution_degrees": sample.get("source_resolution_degrees"),
                "source_raster_id": sample.get("source_raster_id"),
                "source_acquisition_date": sample.get("source_acquisition_date"),
                "retrieved_at": batch.retrieved_at,
                "warnings": batch.warnings,
            }
        )
