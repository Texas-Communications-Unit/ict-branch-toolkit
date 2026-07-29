import json

from rest_framework import serializers

from apps.accounts.models import Role

from .field_policy import filter_assignment_snapshot
from .models import (
    COLLABORATION_SECTIONS,
    CollaborationChange,
    CollaborationResolution,
    PresenceLease,
    SensitiveFieldRule,
)


class CollaborationMutationSerializer(serializers.Serializer):
    client_mutation_id = serializers.UUIDField()
    device_id = serializers.UUIDField()
    revision = serializers.UUIDField()
    operation = serializers.ChoiceField(choices=CollaborationChange.Operation.choices)
    object_id = serializers.UUIDField(required=False, allow_null=True)
    section = serializers.ChoiceField(choices=COLLABORATION_SECTIONS, default="ics205")
    base_version = serializers.IntegerField(min_value=1)
    changes = serializers.DictField()

    def validate_changes(self, value):
        if len(value) > 64:
            raise serializers.ValidationError("A mutation cannot affect more than 64 fields.")
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        if len(encoded) > 65_536:
            raise serializers.ValidationError("A mutation payload cannot exceed 64 KiB.")
        return value

    def validate(self, attrs):
        operation = attrs["operation"]
        object_id = attrs.get("object_id")
        requires_object = operation in {
            CollaborationChange.Operation.ASSIGNMENT_UPDATE,
            CollaborationChange.Operation.ASSIGNMENT_DELETE,
        }
        if requires_object and not object_id:
            raise serializers.ValidationError(
                {"object_id": "This operation requires an assignment identifier."}
            )
        if not requires_object and object_id:
            raise serializers.ValidationError(
                {"object_id": "This operation does not accept an object identifier."}
            )
        return attrs


class CollaborationChangeSerializer(serializers.ModelSerializer):
    resolution = serializers.SerializerMethodField()

    class Meta:
        model = CollaborationChange
        fields = [
            "id",
            "client_mutation_id",
            "revision",
            "actor",
            "device_id",
            "operation",
            "object_id",
            "section",
            "base_version",
            "resulting_version",
            "affected_fields",
            "proposed_snapshot",
            "current_snapshot",
            "payload_sha256",
            "disposition",
            "result",
            "resolution",
            "created_at",
        ]

    def get_resolution(self, change) -> dict | None:
        try:
            resolution = change.resolution
        except CollaborationResolution.DoesNotExist:
            return None
        return {
            "id": str(resolution.id),
            "decision": resolution.decision,
            "explanation": resolution.explanation,
            "replacement_change": (
                str(resolution.replacement_change_id) if resolution.replacement_change_id else None
            ),
            "resolved_by": resolution.resolved_by_id,
            "created_at": resolution.created_at,
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)
        user = self.context["request"].user
        incident = instance.incident
        if instance.operation.startswith("assignment."):
            data["proposed_snapshot"] = filter_assignment_snapshot(
                user=user,
                incident=incident,
                snapshot=data["proposed_snapshot"],
                request=self.context["request"],
            )
            data["current_snapshot"] = filter_assignment_snapshot(
                user=user,
                incident=incident,
                snapshot=data["current_snapshot"],
                request=self.context["request"],
            )
        return data


class ConflictResolutionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=CollaborationResolution.Decision.choices)
    explanation = serializers.CharField(max_length=500)
    replacement_change = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs):
        decision = attrs["decision"]
        replacement = attrs.get("replacement_change")
        if (
            decision
            in {
                CollaborationResolution.Decision.REAPPLY,
                CollaborationResolution.Decision.REPLACE,
            }
            and not replacement
        ):
            raise serializers.ValidationError(
                {"replacement_change": "Reapply and replace require a saved replacement change."}
            )
        if decision == CollaborationResolution.Decision.DISCARD and replacement:
            raise serializers.ValidationError(
                {"replacement_change": "Discard cannot identify a replacement change."}
            )
        return attrs


class PresenceHeartbeatSerializer(serializers.Serializer):
    revision = serializers.UUIDField()
    device_id = serializers.UUIDField()
    section = serializers.ChoiceField(choices=COLLABORATION_SECTIONS, default="ics205")
    mode = serializers.ChoiceField(choices=PresenceLease.Mode.choices)


class PresenceLeaseSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    is_current_user = serializers.SerializerMethodField()

    class Meta:
        model = PresenceLease
        fields = [
            "id",
            "revision",
            "device_id",
            "section",
            "mode",
            "sequence",
            "expires_at",
            "last_seen_at",
            "display_name",
            "is_current_user",
        ]

    def get_display_name(self, lease) -> str:
        return lease.user.get_full_name() or lease.user.get_username()

    def get_is_current_user(self, lease) -> bool:
        return lease.user_id == self.context["request"].user.id


class SensitiveFieldRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = SensitiveFieldRule
        fields = [
            "id",
            "incident",
            "resource_type",
            "field_name",
            "unauthorized_visibility",
            "view_roles",
            "edit_roles",
            "log_reads",
            "version",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "version",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]

    def validate_view_roles(self, value):
        if not isinstance(value, list) or len(value) != len(set(value)):
            raise serializers.ValidationError("Provide a unique array of roles.")
        if any(role not in Role.values for role in value):
            raise serializers.ValidationError("A role is not recognized.")
        return value

    def validate_edit_roles(self, value):
        return self.validate_view_roles(value)

    def validate(self, attrs):
        view_roles = attrs.get("view_roles", getattr(self.instance, "view_roles", []))
        edit_roles = attrs.get("edit_roles", getattr(self.instance, "edit_roles", []))
        if not set(edit_roles).issubset(set(view_roles)):
            raise serializers.ValidationError(
                {"edit_roles": "A role cannot edit a field it is not allowed to view."}
            )
        return attrs
