from django.conf import settings
from rest_framework import serializers

from .models import OfflineConflictResolution, OfflineMutationReceipt, OfflinePackage


class OfflinePackageSelectionSerializer(serializers.Serializer):
    revision_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        max_length=5,
    )
    resource_release_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
        max_length=10,
    )
    site_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
        max_length=100,
    )
    terrain_analysis_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
        max_length=50,
    )
    attachment_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
        max_length=0,
        help_text="Attachments are not an offline-capable subsystem in this release.",
    )
    include_map = serializers.BooleanField(default=False)

    def validate(self, attrs):
        for key in (
            "revision_ids",
            "resource_release_ids",
            "site_ids",
            "terrain_analysis_ids",
        ):
            if len(attrs[key]) != len(set(attrs[key])):
                raise serializers.ValidationError({key: "Select each record only once."})
        if attrs["include_map"] and not attrs["site_ids"]:
            raise serializers.ValidationError(
                {"site_ids": "Select at least one site when including the offline map."}
            )
        return attrs


class CreateOfflinePackageSerializer(serializers.Serializer):
    incident = serializers.UUIDField()
    device_id = serializers.UUIDField()
    expires_in_hours = serializers.IntegerField(
        min_value=1,
        max_value=settings.ICT_OFFLINE_MAX_TTL_HOURS,
        default=settings.ICT_OFFLINE_DEFAULT_TTL_HOURS,
    )
    selection = OfflinePackageSelectionSerializer()


class OfflineConflictResolutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfflineConflictResolution
        fields = ["id", "receipt", "decision", "explanation", "resolved_by", "created_at"]
        read_only_fields = fields


class OfflineMutationReceiptSerializer(serializers.ModelSerializer):
    resolution = OfflineConflictResolutionSerializer(read_only=True)

    class Meta:
        model = OfflineMutationReceipt
        fields = [
            "id",
            "package",
            "sequence",
            "actor_id_snapshot",
            "device_id",
            "operation",
            "object_id",
            "revision_id",
            "previous_hash",
            "payload_sha256",
            "mutation_sha256",
            "base_updated_at",
            "occurred_at_client",
            "status",
            "result",
            "received_at",
            "resolution",
        ]
        read_only_fields = fields


class OfflinePackageSerializer(serializers.ModelSerializer):
    current_status = serializers.SerializerMethodField()
    payload_snapshot = serializers.SerializerMethodField()
    receipts = OfflineMutationReceiptSerializer(
        source="mutation_receipts",
        many=True,
        read_only=True,
    )

    class Meta:
        model = OfflinePackage
        fields = [
            "id",
            "incident",
            "requested_by",
            "device_id",
            "status",
            "current_status",
            "scope",
            "payload_snapshot",
            "manifest",
            "manifest_sha256",
            "last_sequence",
            "last_chain_sha256",
            "expires_at",
            "created_at",
            "updated_at",
            "locked_at",
            "revoked_at",
            "purged_at",
            "receipts",
        ]
        read_only_fields = fields

    def get_current_status(self, package) -> str:
        from .services import package_current_status

        request = self.context.get("request")
        return package_current_status(package, getattr(request, "user", None))

    def get_payload_snapshot(self, package) -> dict:
        request = self.context.get("request")
        if self.get_current_status(package) != OfflinePackage.Status.ACTIVE:
            return {}
        if request and package.requested_by_id != request.user.pk:
            return {}
        return package.payload_snapshot


class OfflinePackageSummarySerializer(serializers.ModelSerializer):
    current_status = serializers.SerializerMethodField()

    class Meta:
        model = OfflinePackage
        fields = [
            "id",
            "incident",
            "requested_by",
            "device_id",
            "status",
            "current_status",
            "scope",
            "manifest_sha256",
            "last_sequence",
            "last_chain_sha256",
            "expires_at",
            "created_at",
            "updated_at",
            "locked_at",
            "revoked_at",
            "purged_at",
        ]
        read_only_fields = fields

    def get_current_status(self, package) -> str:
        from .services import package_current_status

        request = self.context.get("request")
        return package_current_status(package, getattr(request, "user", None))


class OfflineMutationSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    sequence = serializers.IntegerField(min_value=1)
    actor_id = serializers.IntegerField(min_value=1)
    device_id = serializers.UUIDField()
    operation = serializers.ChoiceField(
        choices=[
            "revision.update",
            "assignment.create",
            "assignment.update",
            "assignment.delete",
        ]
    )
    object_id = serializers.UUIDField(required=False, allow_null=True)
    revision_id = serializers.UUIDField()
    previous_hash = serializers.RegexField(r"^[0-9a-f]{64}$")
    payload_sha256 = serializers.RegexField(r"^[0-9a-f]{64}$")
    mutation_sha256 = serializers.RegexField(r"^[0-9a-f]{64}$")
    payload = serializers.JSONField(default=dict)
    base_updated_at = serializers.DateTimeField(required=False, allow_null=True)
    occurred_at_client = serializers.DateTimeField()


class SynchronizeOfflinePackageSerializer(serializers.Serializer):
    client_now = serializers.DateTimeField()
    mutations = OfflineMutationSerializer(
        many=True,
        min_length=1,
        max_length=settings.ICT_OFFLINE_MAX_QUEUE_ITEMS,
    )

    def validate_mutations(self, mutations):
        sequences = [item["sequence"] for item in mutations]
        if sequences != sorted(sequences):
            raise serializers.ValidationError("Mutations must be submitted in sequence order.")
        if len(sequences) != len(set(sequences)):
            raise serializers.ValidationError("Each sequence may appear only once per request.")
        return mutations


class ResolveOfflineConflictSerializer(serializers.Serializer):
    mutation_id = serializers.UUIDField()
    decision = serializers.ChoiceField(choices=OfflineConflictResolution.Decision.choices)
    explanation = serializers.CharField(min_length=1, max_length=500)
