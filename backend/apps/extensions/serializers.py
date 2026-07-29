import json

from rest_framework import serializers

from apps.incidents.models import Incident
from apps.plans.models import PlanRevision

from .models import ExtensionExecution, ExtensionInstallation


class ExtensionCatalogEntrySerializer(serializers.Serializer):
    manifest = serializers.DictField(read_only=True)
    installed = serializers.BooleanField(read_only=True)
    enabled = serializers.BooleanField(read_only=True)
    compatible = serializers.BooleanField(read_only=True)
    installation_id = serializers.UUIDField(read_only=True, allow_null=True)
    operator_message = serializers.CharField(read_only=True)


class ExtensionInstallRequestSerializer(serializers.Serializer):
    extension_key = serializers.SlugField(max_length=120)
    contract_version = serializers.CharField(max_length=20)


class ExtensionInstallationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExtensionInstallation
        fields = [
            "id",
            "extension_key",
            "extension_version",
            "contract_version",
            "manifest_snapshot",
            "manifest_sha256",
            "enabled",
            "installed_by",
            "installed_at",
            "updated_by",
            "updated_at",
        ]
        read_only_fields = fields


class CreateExtensionExecutionSerializer(serializers.Serializer):
    extension_key = serializers.SlugField(max_length=120)
    contract_version = serializers.CharField(max_length=20)
    capability = serializers.SlugField(max_length=120)
    incident = serializers.PrimaryKeyRelatedField(
        queryset=Incident.objects.filter(archived_at__isnull=True)
    )
    source_revision = serializers.PrimaryKeyRelatedField(
        queryset=PlanRevision.objects.select_related("plan__incident")
    )
    inputs = serializers.JSONField()

    def validate_inputs(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Extension inputs must be an object.")
        if set(value) != {"minimum_assignment_count"}:
            raise serializers.ValidationError(
                "The synthetic example accepts only minimum_assignment_count."
            )
        minimum = value["minimum_assignment_count"]
        if isinstance(minimum, bool) or not isinstance(minimum, int) or not 1 <= minimum <= 1000:
            raise serializers.ValidationError(
                "minimum_assignment_count must be an integer from 1 through 1000."
            )
        encoded = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        if len(encoded) > 16_384:
            raise serializers.ValidationError("Extension inputs cannot exceed 16 KiB.")
        return value


class ExtensionExecutionSerializer(serializers.ModelSerializer):
    source_revision_number = serializers.IntegerField(
        source="source_revision.number",
        read_only=True,
    )

    class Meta:
        model = ExtensionExecution
        fields = [
            "id",
            "extension_key",
            "extension_version",
            "contract_version",
            "capability",
            "capability_kind",
            "incident",
            "source_revision",
            "source_revision_number",
            "input_snapshot",
            "input_sha256",
            "result_snapshot",
            "result_sha256",
            "output_classification",
            "status",
            "failure_code",
            "failure_message",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields
