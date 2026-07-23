from django.db import transaction
from rest_framework import serializers

from .models import Assignment, AssignmentRelationship, ICS205Plan, PlanRevision
from .services import ensure_draft, resource_snapshot


class AssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Assignment
        fields = "__all__"
        read_only_fields = ["id", "resource_snapshot", "created_at", "updated_at"]

    def validate(self, attrs):
        revision = attrs.get("revision", getattr(self.instance, "revision", None))
        if revision:
            ensure_draft(revision)
        if self.instance and revision != self.instance.revision:
            raise serializers.ValidationError({"revision": "The revision cannot be changed."})
        if attrs.get("conventional_channel") and attrs.get("trunked_talkgroup"):
            raise serializers.ValidationError("Choose one resource type.")
        return attrs

    def create(self, validated_data):
        validated_data["resource_snapshot"] = resource_snapshot(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        ensure_draft(instance.revision)
        if "conventional_channel" in validated_data or "trunked_talkgroup" in validated_data:
            merged = {
                "channel_name": instance.channel_name,
                "conventional_channel": instance.conventional_channel,
                "trunked_talkgroup": instance.trunked_talkgroup,
                **validated_data,
            }
            validated_data["resource_snapshot"] = resource_snapshot(merged)
        return super().update(instance, validated_data)


class RelationshipSerializer(serializers.ModelSerializer):
    assignments = serializers.PrimaryKeyRelatedField(many=True, queryset=Assignment.objects.all())

    class Meta:
        model = AssignmentRelationship
        fields = ["id", "revision", "relationship_type", "label", "assignments", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        revision = attrs.get("revision", getattr(self.instance, "revision", None))
        ensure_draft(revision)
        assignments = attrs.get("assignments", [])
        if any(item.revision_id != revision.id for item in assignments):
            raise serializers.ValidationError(
                {"assignments": "All assignments must belong to this revision."}
            )
        relationship_type = attrs.get(
            "relationship_type", getattr(self.instance, "relationship_type", None)
        )
        if relationship_type == AssignmentRelationship.Type.PATCH and len(assignments) < 2:
            raise serializers.ValidationError(
                {"assignments": "A Patch relationship requires at least two assignments."}
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        assignments = validated_data.pop("assignments")
        relationship = AssignmentRelationship.objects.create(**validated_data)
        relationship.assignments.set(assignments)
        return relationship


class PlanRevisionSerializer(serializers.ModelSerializer):
    assignments = AssignmentSerializer(many=True, read_only=True)
    relationships = RelationshipSerializer(many=True, read_only=True)
    is_locked = serializers.BooleanField(read_only=True)

    class Meta:
        model = PlanRevision
        fields = [
            "id",
            "plan",
            "number",
            "status",
            "is_locked",
            "prepared_by_name",
            "prepared_by_position",
            "prepared_at",
            "copied_from",
            "created_by",
            "approved_by",
            "approved_at",
            "created_at",
            "updated_at",
            "assignments",
            "relationships",
        ]
        read_only_fields = [
            "id",
            "number",
            "status",
            "copied_from",
            "created_by",
            "approved_by",
            "approved_at",
            "created_at",
            "updated_at",
            "is_locked",
        ]

    def validate(self, attrs):
        if self.instance:
            ensure_draft(self.instance)
            if attrs.get("plan", self.instance.plan) != self.instance.plan:
                raise serializers.ValidationError({"plan": "The plan cannot be changed."})
        return attrs


class PlanSerializer(serializers.ModelSerializer):
    revisions = PlanRevisionSerializer(many=True, read_only=True)

    class Meta:
        model = ICS205Plan
        fields = [
            "id",
            "incident",
            "operational_period",
            "title",
            "created_by",
            "created_at",
            "archived_at",
            "revisions",
        ]
        read_only_fields = ["id", "created_by", "created_at", "archived_at"]

    def validate(self, attrs):
        incident = attrs.get("incident", getattr(self.instance, "incident", None))
        period = attrs.get("operational_period", getattr(self.instance, "operational_period", None))
        if period and incident and period.incident_id != incident.id:
            raise serializers.ValidationError(
                {"operational_period": "Operational period must belong to the incident."}
            )
        if self.instance and (
            incident != self.instance.incident or period != self.instance.operational_period
        ):
            raise serializers.ValidationError("Incident and operational period cannot be changed.")
        return attrs
