from rest_framework import serializers

from .models import RFAnalysisInputSnapshot, SubscriberProfile, SubscriberProfileVersion
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
