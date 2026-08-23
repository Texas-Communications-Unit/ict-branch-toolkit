from rest_framework import serializers

from .crypto import decrypt_value
from .models import Asset, AssetCheckout, ProgrammingRecord


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
            "status",
            "notes",
            "created_by_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["status", "created_by_username", "created_at", "updated_at"]

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
    asset = serializers.UUIDField()
    assigned_name = serializers.CharField(max_length=200)
    assigned_organization = serializers.CharField(max_length=200)
    driver_license_jurisdiction = serializers.CharField(min_length=2, max_length=8)
    driver_license_number = serializers.CharField(min_length=4, max_length=32, write_only=True)


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
