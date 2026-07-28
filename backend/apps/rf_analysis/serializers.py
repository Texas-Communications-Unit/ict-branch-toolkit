from decimal import Decimal

from rest_framework import serializers

from apps.sites.models import RadioSite

from .models import (
    ElevationSnapshot,
    HAATCalculation,
    RFAnalysisInputSnapshot,
    SubscriberProfile,
    SubscriberProfileVersion,
)
from .services import VERSION_EDITABLE_FIELDS, normalize_version_attrs


class SubscriberProfileVersionInputSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriberProfileVersion
        fields = VERSION_EDITABLE_FIELDS

    def validate(self, attrs):
        return normalize_version_attrs(None, attrs)


class SubscriberProfileVersionSerializer(serializers.ModelSerializer):
    is_locked = serializers.BooleanField(read_only=True)

    class Meta:
        model = SubscriberProfileVersion
        fields = [
            "id",
            "profile",
            "number",
            "status",
            *VERSION_EDITABLE_FIELDS,
            "erp_calculation_path",
            "input_snapshot",
            "input_sha256",
            "created_by",
            "approved_by",
            "approved_at",
            "created_at",
            "updated_at",
            "is_locked",
        ]
        read_only_fields = [
            "id",
            "profile",
            "number",
            "status",
            "erp_calculation_path",
            "input_snapshot",
            "input_sha256",
            "created_by",
            "approved_by",
            "approved_at",
            "created_at",
            "updated_at",
            "is_locked",
        ]

    def validate(self, attrs):
        if self.instance and self.instance.is_locked:
            raise serializers.ValidationError(
                "Approved subscriber profile versions are immutable. Copy to a new draft."
            )
        return normalize_version_attrs(self.instance, attrs)


class SubscriberProfileSerializer(serializers.ModelSerializer):
    initial_version = SubscriberProfileVersionInputSerializer(
        write_only=True,
        required=False,
    )
    versions = SubscriberProfileVersionSerializer(many=True, read_only=True)

    class Meta:
        model = SubscriberProfile
        fields = [
            "id",
            "incident",
            "name",
            "profile_type",
            "description",
            "initial_version",
            "versions",
            "created_by",
            "created_at",
            "updated_at",
            "archived_at",
        ]
        read_only_fields = [
            "id",
            "versions",
            "created_by",
            "created_at",
            "updated_at",
            "archived_at",
        ]

    def validate(self, attrs):
        if self.instance:
            if "initial_version" in attrs:
                raise serializers.ValidationError(
                    {"initial_version": "Initial version is accepted only when creating a profile."}
                )
            if attrs.get("incident", self.instance.incident) != self.instance.incident:
                raise serializers.ValidationError(
                    {"incident": "The profile incident cannot be changed."}
                )
            if self.instance.archived_at:
                raise serializers.ValidationError("Archived subscriber profiles cannot be changed.")
        elif "initial_version" not in attrs:
            raise serializers.ValidationError(
                {"initial_version": "Provide the first draft subscriber profile version."}
            )
        return attrs

    def create(self, validated_data):
        initial_version = validated_data.pop("initial_version")
        profile = SubscriberProfile.objects.create(**validated_data)
        SubscriberProfileVersion.objects.create(
            profile=profile,
            number=1,
            created_by=profile.created_by,
            **initial_version,
        )
        return profile


class RFAnalysisInputSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = RFAnalysisInputSnapshot
        fields = [
            "id",
            "incident",
            "profile_version",
            "label",
            "input_snapshot",
            "input_sha256",
            "created_by",
            "approved_by",
            "approved_at",
            "created_at",
            "archived_at",
        ]
        read_only_fields = fields


class CreateRFAnalysisInputSnapshotSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=200, allow_blank=False, trim_whitespace=True)


class ElevationSnapshotSummarySerializer(serializers.ModelSerializer):
    current_state = serializers.CharField(read_only=True)

    class Meta:
        model = ElevationSnapshot
        fields = [
            "id",
            "incident",
            "site",
            "query_sha256",
            "provider",
            "dataset_product",
            "horizontal_crs",
            "vertical_crs",
            "target_vertical_crs",
            "resolution_m",
            "source_version",
            "source_retrieved_at",
            "license_terms_url",
            "permitted_use",
            "coverage",
            "source_content_sha256",
            "acquisition_state",
            "current_state",
            "sample_sha256",
            "transformation",
            "warnings",
            "retrieved_at",
            "stale_at",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields


class ElevationSnapshotSerializer(ElevationSnapshotSummarySerializer):
    class Meta(ElevationSnapshotSummarySerializer.Meta):
        fields = [
            *ElevationSnapshotSummarySerializer.Meta.fields,
            "query_snapshot",
            "sample_snapshot",
        ]
        read_only_fields = fields


class HAATCalculationSerializer(serializers.ModelSerializer):
    is_locked = serializers.BooleanField(read_only=True)
    elevation = ElevationSnapshotSummarySerializer(source="elevation_snapshot", read_only=True)
    site_name = serializers.CharField(source="site.name", read_only=True)
    profile_name = serializers.CharField(source="profile_version.profile.name", read_only=True)
    profile_version_number = serializers.IntegerField(
        source="profile_version.number",
        read_only=True,
    )
    rf_input_label = serializers.CharField(source="rf_input_snapshot.label", read_only=True)

    class Meta:
        model = HAATCalculation
        fields = [
            "id",
            "incident",
            "site",
            "site_name",
            "profile_version",
            "profile_name",
            "profile_version_number",
            "rf_input_snapshot",
            "rf_input_label",
            "elevation_snapshot",
            "elevation",
            "supersedes",
            "status",
            "calculation_state",
            "method",
            "method_version",
            "radial_count",
            "start_azimuth_deg",
            "sampling_interval_m",
            "inner_distance_m",
            "outer_distance_m",
            "rounding_m",
            "antenna_agl_m",
            "site_elevation_m",
            "antenna_amsl_m",
            "average_terrain_m",
            "haat_m",
            "sample_count",
            "excluded_sample_count",
            "algorithm_snapshot",
            "exclusions",
            "warnings",
            "result_snapshot",
            "result_sha256",
            "created_by",
            "approved_by",
            "approved_at",
            "created_at",
            "is_locked",
        ]
        read_only_fields = fields


class CreateHAATCalculationSerializer(serializers.Serializer):
    site = serializers.PrimaryKeyRelatedField(queryset=RadioSite.objects.all())
    rf_input_snapshot = serializers.PrimaryKeyRelatedField(
        queryset=RFAnalysisInputSnapshot.objects.select_related(
            "incident",
            "profile_version__profile",
        )
    )
    radial_count = serializers.IntegerField(default=8, min_value=4, max_value=360)
    start_azimuth_deg = serializers.DecimalField(
        default=Decimal("0"),
        max_digits=6,
        decimal_places=3,
        min_value=Decimal("0"),
        max_value=Decimal("359.999"),
    )
    sampling_interval_m = serializers.IntegerField(
        default=1000,
        min_value=10,
        max_value=100_000,
    )
    inner_distance_m = serializers.IntegerField(
        default=3000,
        min_value=1,
        max_value=100_000,
    )
    outer_distance_m = serializers.IntegerField(
        default=16_000,
        min_value=1,
        max_value=100_000,
    )
    rounding_m = serializers.DecimalField(
        default=Decimal("0.1"),
        max_digits=7,
        decimal_places=3,
        min_value=Decimal("0.001"),
        max_value=Decimal("100"),
    )
    force_refresh = serializers.BooleanField(default=False)

    def validate(self, attrs):
        if attrs["site"].incident_id != attrs["rf_input_snapshot"].incident_id:
            raise serializers.ValidationError(
                "Site and RF analysis input snapshot must belong to the same incident."
            )
        if attrs["outer_distance_m"] <= attrs["inner_distance_m"]:
            raise serializers.ValidationError(
                {"outer_distance_m": "Outer distance must be greater than inner distance."}
            )
        return attrs
