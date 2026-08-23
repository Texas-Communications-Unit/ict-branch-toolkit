from rest_framework import serializers

from .crypto import decrypt_value
from .models import (
    Asset,
    AssetAttachment,
    AssetCheckout,
    AssetImportBatch,
    ChargingRecord,
    MaintenanceRecord,
    ProgrammingRecord,
)


class AssetSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = Asset
        fields = [
            "id",
            "asset_id",
            "category",
            "parent",
            "manufacturer",
            "model",
            "serial_number",
            "alias",
            "asset_subtype",
            "flash_code",
            "subscriber_id",
            "system_ids",
            "acquisition_date",
            "last_calibrated_at",
            "status",
            "notes",
            "created_by_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_by_username", "created_at", "updated_at"]

    def validate_parent(self, parent):
        instance = self.instance
        ancestor = parent
        while ancestor and instance:
            if ancestor.pk == instance.pk:
                raise serializers.ValidationError(
                    "This parent would create a circular asset relationship."
                )
            ancestor = ancestor.parent
        return parent

    def validate_status(self, value):
        if not self.instance and value == Asset.Status.CHECKED_OUT:
            raise serializers.ValidationError("Use accountable checkout to check out an asset.")
        if (
            self.instance
            and self.instance.status == Asset.Status.CHECKED_OUT
            and value != Asset.Status.CHECKED_OUT
        ):
            raise serializers.ValidationError("Return the asset before changing its status.")
        return value


class AssetCheckoutSerializer(serializers.ModelSerializer):
    asset_detail = AssetSerializer(source="asset", read_only=True)
    driver_license_number = serializers.SerializerMethodField()
    checked_out_by_username = serializers.CharField(
        source="checked_out_by.username", read_only=True
    )
    returned_by_username = serializers.CharField(source="returned_by.username", read_only=True)
    hold_resolved_by_username = serializers.CharField(
        source="hold_resolved_by.username", read_only=True
    )

    class Meta:
        model = AssetCheckout
        fields = [
            "id",
            "incident",
            "asset",
            "asset_detail",
            "assigned_name",
            "assigned_organization",
            "point_of_contact",
            "phone_number",
            "mailing_address",
            "assignment_notes",
            "driver_license_jurisdiction",
            "driver_license_number",
            "driver_license_last_four",
            "state",
            "checked_out_by_username",
            "checked_out_at",
            "returned_by_username",
            "returned_at",
            "return_condition",
            "hold_reason",
            "hold_resolved_by_username",
            "hold_resolved_at",
            "hold_resolution_note",
        ]

    def get_driver_license_number(self, obj) -> str | None:
        if not obj.driver_license_ciphertext:
            return None
        return decrypt_value(
            obj.driver_license_ciphertext,
            context=obj.driver_license_context,
        )


class AssetCheckoutCreateSerializer(serializers.Serializer):
    incident = serializers.UUIDField()
    assets = serializers.ListField(child=serializers.UUIDField(), min_length=1, max_length=25)
    assigned_name = serializers.CharField(max_length=200)
    assigned_organization = serializers.CharField(max_length=200)
    point_of_contact = serializers.CharField(max_length=200, allow_blank=True, required=False)
    phone_number = serializers.CharField(max_length=40, allow_blank=True, required=False)
    mailing_address = serializers.CharField(max_length=1000, allow_blank=True, required=False)
    assignment_notes = serializers.CharField(max_length=2000, allow_blank=True, required=False)
    driver_license_jurisdiction = serializers.CharField(min_length=2, max_length=8)
    driver_license_number = serializers.CharField(min_length=4, max_length=32, write_only=True)

    def validate_assets(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError("Each asset may be selected only once.")
        return value


class AssetReturnSerializer(serializers.Serializer):
    condition = serializers.ChoiceField(choices=AssetCheckout.ReturnCondition.choices)
    hold_reason = serializers.CharField(max_length=2000, allow_blank=True, required=False)

    def validate(self, attrs):
        if (
            attrs["condition"] != AssetCheckout.ReturnCondition.NORMAL
            and not attrs.get("hold_reason", "").strip()
        ):
            raise serializers.ValidationError({"hold_reason": "Explain the accountability hold."})
        return attrs


class AccountabilityHoldResolutionSerializer(serializers.Serializer):
    asset_status = serializers.ChoiceField(
        choices=[
            Asset.Status.IN_SERVICE,
            Asset.Status.MAINTENANCE,
            Asset.Status.RETIRED,
        ]
    )
    resolution_note = serializers.CharField(max_length=2000)


class ProgrammingRecordSerializer(serializers.ModelSerializer):
    confirmed_by_username = serializers.CharField(source="confirmed_by.username", read_only=True)

    class Meta:
        model = ProgrammingRecord
        fields = [
            "id",
            "asset",
            "template_name",
            "template_version",
            "programmed_at",
            "codeplug_backup_saved",
            "backup_note",
            "confirmed_by_username",
            "confirmed_at",
        ]
        read_only_fields = ["confirmed_by_username", "confirmed_at"]

    def validate_codeplug_backup_saved(self, value):
        if not value:
            raise serializers.ValidationError(
                "Confirm the codeplug backup was saved before completing the record."
            )
        return value


class MaintenanceRecordSerializer(serializers.ModelSerializer):
    recorded_by_username = serializers.CharField(source="recorded_by.username", read_only=True)

    class Meta:
        model = MaintenanceRecord
        fields = [
            "id",
            "asset",
            "kind",
            "performed_at",
            "technician",
            "notes",
            "return_to_service",
            "recorded_by_username",
            "recorded_at",
        ]
        read_only_fields = ["recorded_by_username", "recorded_at"]


class ChargingRecordSerializer(serializers.ModelSerializer):
    recorded_by_username = serializers.CharField(source="recorded_by.username", read_only=True)

    class Meta:
        model = ChargingRecord
        fields = [
            "id",
            "asset",
            "started_at",
            "completed_at",
            "notes",
            "recorded_by_username",
            "recorded_at",
        ]
        read_only_fields = ["recorded_by_username", "recorded_at"]

    def validate(self, attrs):
        if attrs.get("completed_at") and attrs["completed_at"] < attrs["started_at"]:
            raise serializers.ValidationError(
                {"completed_at": "Completion cannot be before charging started."}
            )
        return attrs


class AssetAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_username = serializers.CharField(source="uploaded_by.username", read_only=True)

    class Meta:
        model = AssetAttachment
        fields = [
            "id",
            "asset",
            "original_name",
            "content_type",
            "size_bytes",
            "description",
            "uploaded_by_username",
            "uploaded_at",
        ]
        read_only_fields = fields


class AssetAttachmentUploadSerializer(serializers.Serializer):
    asset = serializers.UUIDField()
    file = serializers.FileField()
    description = serializers.CharField(max_length=500, allow_blank=True, required=False)


class AssetImportPreviewSerializer(serializers.Serializer):
    file = serializers.FileField()


class AssetImportCommitSerializer(serializers.Serializer):
    batch_id = serializers.UUIDField()


class AssetImportBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetImportBatch
        fields = [
            "id",
            "source_name",
            "source_sha256",
            "rows",
            "errors",
            "row_count",
            "valid_count",
            "status",
            "created_at",
            "committed_at",
        ]
        read_only_fields = fields
