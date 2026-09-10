import re
from dataclasses import asdict

from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .coordinates import CoordinateError, coordinate_formats, parse_coordinate
from .geocoders import GeocoderError, configured_geocoder
from .what3words import What3WordsError, configured_what3words


WHAT3WORDS_RE = re.compile(r"^(?:https?://(?:www\.)?what3words\.com/)?/?/?/?([a-z]+\.[a-z]+\.[a-z]+)$", re.IGNORECASE)


class LocationResolveSerializer(serializers.Serializer):
    query = serializers.CharField(max_length=500, trim_whitespace=True)
    external_lookup_allowed = serializers.BooleanField(required=False, default=False)


def _result(label: str, latitude: float, longitude: float, provider: str, original: str):
    return {
        "label": label,
        "latitude": round(latitude, 6),
        "longitude": round(longitude, 6),
        "crs": "EPSG:4326",
        "provider": provider,
        "original_query": original,
        "formats": coordinate_formats(latitude, longitude),
    }


def _what3words_value(query: str) -> str | None:
    match = WHAT3WORDS_RE.fullmatch(query.strip())
    return match.group(1).lower() if match else None


class LocationResolveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LocationResolveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        query = serializer.validated_data["query"]
        external_allowed = serializer.validated_data["external_lookup_allowed"]

        try:
            parsed = parse_coordinate(query)
        except CoordinateError:
            parsed = None

        if parsed is not None:
            return Response(
                {
                    "original_query": query,
                    "resolution_method": "local_coordinate",
                    "external_lookup_performed": False,
                    "provider": "local-coordinate-parser",
                    "configured": True,
                    "results": [
                        _result(
                            coordinate_formats(parsed.latitude, parsed.longitude)["decimal"],
                            parsed.latitude,
                            parsed.longitude,
                            "local-coordinate-parser",
                            query,
                        )
                    ],
                }
            )

        words = _what3words_value(query)
        if words:
            provider = configured_what3words()
            if not external_allowed:
                return Response(
                    {
                        "original_query": query,
                        "resolution_method": "what3words",
                        "external_lookup_performed": False,
                        "provider": provider.name,
                        "configured": provider.name != "disabled",
                        "blocked_reason": "External lookup was not approved for this query.",
                        "results": [],
                    }
                )
            try:
                matches = provider.search(words)
            except What3WordsError:
                return Response(
                    {"detail": "The what3words provider is currently unavailable."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            return Response(
                {
                    "original_query": query,
                    "resolution_method": "what3words",
                    "external_lookup_performed": provider.name != "disabled",
                    "provider": provider.name,
                    "configured": provider.name != "disabled",
                    "results": [
                        _result(item.label, item.latitude, item.longitude, item.provider, query)
                        for item in matches
                    ],
                }
            )

        provider = configured_geocoder()
        if not external_allowed:
            return Response(
                {
                    "original_query": query,
                    "resolution_method": "geocoder",
                    "external_lookup_performed": False,
                    "provider": provider.name,
                    "configured": provider.name != "disabled",
                    "blocked_reason": "External lookup was not approved for this query.",
                    "results": [],
                }
            )
        try:
            matches = provider.search(query)
        except GeocoderError:
            return Response(
                {"detail": "Geocoding service is currently unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(
            {
                "original_query": query,
                "resolution_method": "geocoder",
                "external_lookup_performed": provider.name != "disabled",
                "provider": provider.name,
                "configured": provider.name != "disabled",
                "results": [
                    _result(item.label, item.latitude, item.longitude, item.provider, query)
                    for item in matches
                ],
            }
        )
