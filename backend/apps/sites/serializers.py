from decimal import Decimal

from rest_framework import serializers

from apps.plans.services import ensure_draft

from .coordinates import CoordinateError, coordinate_formats, parse_coordinate
from .models import ManualRing, RadioSite, SiteAssignment
from .services import validate_site_link


class RadioSiteSerializer(serializers.ModelSerializer):
    coordinate_text = serializers.CharField(write_only=True, required=False, allow_blank=False)
    latitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, min_value=-90, max_value=90
    )
    longitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, min_value=-180, max_value=180
    )
    coordinate_formats = serializers.SerializerMethodField()
    rings = serializers.SerializerMethodField()

    class Meta:
        model = RadioSite
        fields = [
            "id",
            "incident",
            "name",
            "description",
            "latitude",
            "longitude",
            "entered_coordinate",
            "coordinate_format",
            "coordinate_text",
            "coordinate_formats",
            "address",
            "source_identity",
            "source_retrieved_at",
            "rings",
            "created_by",
            "created_at",
            "updated_at",
            "archived_at",
        ]
        read_only_fields = [
            "id",
            "coordinate_formats",
            "rings",
            "created_by",
            "created_at",
            "updated_at",
            "archived_at",
        ]

    def get_coordinate_formats(self, obj) -> dict[str, str]:
        return coordinate_formats(float(obj.latitude), float(obj.longitude))

    def get_rings(self, obj) -> list[dict]:
        return ManualRingSerializer(obj.rings.all(), many=True).data

    def validate(self, attrs):
        coordinate_text = attrs.pop("coordinate_text", None)
        if coordinate_text:
            try:
                parsed = parse_coordinate(coordinate_text)
            except CoordinateError as exc:
                raise serializers.ValidationError({"coordinate_text": str(exc)}) from exc
            coordinate_format = attrs.get("coordinate_format")
            if coordinate_format != RadioSite.CoordinateFormat.ADDRESS:
                coordinate_format = parsed.input_format
            attrs.update(
                {
                    "latitude": Decimal(f"{parsed.latitude:.6f}"),
                    "longitude": Decimal(f"{parsed.longitude:.6f}"),
                    "entered_coordinate": coordinate_text,
                    "coordinate_format": coordinate_format,
                }
            )
        latitude = attrs.get("latitude", getattr(self.instance, "latitude", None))
        longitude = attrs.get("longitude", getattr(self.instance, "longitude", None))
        if latitude is None or longitude is None:
            raise serializers.ValidationError("Provide both latitude and longitude.")
        if (
            self.instance
            and attrs.get("incident", self.instance.incident) != self.instance.incident
        ):
            raise serializers.ValidationError({"incident": "The site incident cannot be changed."})
        return attrs


class ManualRingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ManualRing
        fields = ["id", "site", "ring_type", "radius_m", "label", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        if self.instance and attrs.get("site", self.instance.site) != self.instance.site:
            raise serializers.ValidationError({"site": "The ring site cannot be changed."})
        return attrs


class SiteAssignmentSerializer(serializers.ModelSerializer):
    site_name = serializers.CharField(source="site.name", read_only=True)
    assignment_label = serializers.SerializerMethodField()

    class Meta:
        model = SiteAssignment
        fields = [
            "id",
            "site",
            "site_name",
            "assignment",
            "assignment_label",
            "site_snapshot",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "site_name",
            "assignment_label",
            "site_snapshot",
            "created_at",
        ]

    def get_assignment_label(self, obj) -> str:
        return (
            f"{obj.assignment.position}. {obj.assignment.function} — {obj.assignment.channel_name}"
        )

    def validate(self, attrs):
        site = attrs.get("site", getattr(self.instance, "site", None))
        assignment = attrs.get("assignment", getattr(self.instance, "assignment", None))
        if self.instance:
            ensure_draft(self.instance.assignment.revision)
            if site != self.instance.site or assignment != self.instance.assignment:
                raise serializers.ValidationError("Site links cannot be reassigned.")
        validate_site_link(site, assignment)
        return attrs


class CoordinateParseSerializer(serializers.Serializer):
    coordinate = serializers.CharField(max_length=240)


class GeocoderQuerySerializer(serializers.Serializer):
    address = serializers.CharField(max_length=500)
