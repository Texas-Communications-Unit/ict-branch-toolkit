from django.db import transaction
from rest_framework import serializers

from apps.accounts.models import Role
from apps.collaboration.field_policy import (
    effective_incident_role,
    enforce_assignment_field_edits,
    filter_assignment_snapshot,
)

from .models import Assignment, AssignmentRelationship, ICS205Plan, PlanRevision
from .services import ensure_draft, resource_snapshot


class AssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Assignment
        fields = "__all__"
        read_only_fields = [
            "id",
            "resource_snapshot",
            "collaboration_version",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        revision = attrs.get("revision", getattr(self.instance, "revision", None))
        if revision:
            ensure_draft(revision)
        if self.instance and revision != self.instance.revision:
            raise serializers.ValidationError({"revision": "The revision cannot be changed."})
        if self.instance is None and "operating_classification" not in attrs:
            raise serializers.ValidationError(
                {
                    "operating_classification": (
                        "Select the assignment operating classification explicitly."
                    )
                }
            )
        if attrs.get("conventional_channel") and attrs.get("trunked_talkgroup"):
            raise serializers.ValidationError("Choose one resource type.")
        profile_version = attrs.get(
            "subscriber_profile_version",
            getattr(self.instance, "subscriber_profile_version", None),
        )
        if profile_version:
            if profile_version.status != profile_version.Status.APPROVED:
                raise serializers.ValidationError(
                    {
                        "subscriber_profile_version": (
                            "Select an approved subscriber programming profile version."
                        )
                    }
                )
            if revision and profile_version.profile.incident_id != revision.plan.incident_id:
                raise serializers.ValidationError(
                    {
                        "subscriber_profile_version": (
                            "The subscriber programming profile must belong to the plan incident."
                        )
                    }
                )

        classification = attrs.get(
            "operating_classification",
            getattr(
                self.instance,
                "operating_classification",
                Assignment.OperatingClassification.NOT_DETERMINED,
            ),
        )
        subtype = attrs.get(
            "technology_subtype",
            getattr(self.instance, "technology_subtype", ""),
        )
        rx_frequency_hz = attrs.get(
            "rx_frequency_hz",
            getattr(self.instance, "rx_frequency_hz", None),
        )
        tx_frequency_hz = attrs.get(
            "tx_frequency_hz",
            getattr(self.instance, "tx_frequency_hz", None),
        )
        has_rx = rx_frequency_hz is not None
        has_tx = tx_frequency_hz is not None
        intent_errors = {}
        if classification == Assignment.OperatingClassification.FIXED_PAIR and not (
            has_rx and has_tx
        ):
            intent_errors["operating_classification"] = (
                "Fixed-frequency pair requires both receive and transmit frequencies."
            )
        elif classification == Assignment.OperatingClassification.TRANSMIT_ONLY and (
            has_rx or not has_tx
        ):
            intent_errors["operating_classification"] = (
                "Broadcast/transmit-only requires a transmit frequency and a blank "
                "receive frequency."
            )
        elif classification == Assignment.OperatingClassification.RECEIVE_ONLY and (
            not has_rx or has_tx
        ):
            intent_errors["operating_classification"] = (
                "Receive-only requires a receive frequency and a blank transmit frequency."
            )
        elif classification in {
            Assignment.OperatingClassification.NAMED_SYSTEM,
            Assignment.OperatingClassification.DYNAMIC_POOL,
        } and (has_rx or has_tx):
            intent_errors["operating_classification"] = (
                "This operating classification intentionally omits fixed receive and "
                "transmit frequencies."
            )
        if classification == Assignment.OperatingClassification.NAMED_SYSTEM:
            if not subtype:
                intent_errors["technology_subtype"] = (
                    "Named system channels require a technology subtype."
                )
        elif subtype:
            intent_errors["technology_subtype"] = (
                "Technology subtype applies only to a named system channel."
            )
        if intent_errors:
            raise serializers.ValidationError(intent_errors)
        request = self.context.get("request")
        if revision and request:
            restricted_changes = {
                field: value
                for field, value in attrs.items()
                if self.instance is not None or value not in ("", None)
            }
            enforce_assignment_field_edits(
                user=request.user,
                incident=revision.plan.incident,
                fields=restricted_changes,
                request=request,
            )
            if {
                "published_contact_fields",
                "contact_publication_purpose",
                "contact_publication_placement",
            } & attrs.keys():
                role = effective_incident_role(
                    request.user,
                    revision.plan.incident,
                    request=request,
                )
                if role not in {
                    Role.ADMINISTRATOR,
                    Role.COML,
                    Role.COMC,
                    Role.COMT,
                }:
                    raise serializers.ValidationError(
                        {
                            "published_contact_fields": (
                                "Your incident role cannot publish restricted contact fields."
                            )
                        }
                    )
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        if not request:
            return data
        return filter_assignment_snapshot(
            user=request.user,
            incident=instance.revision.plan.incident,
            snapshot=data,
            request=request,
        )

    def create(self, validated_data):
        validated_data["resource_snapshot"] = resource_snapshot(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        ensure_draft(instance.revision)
        if {
            "conventional_channel",
            "trunked_talkgroup",
            "subscriber_profile_version",
        } & validated_data.keys():
            merged = {
                "channel_name": instance.channel_name,
                "conventional_channel": instance.conventional_channel,
                "trunked_talkgroup": instance.trunked_talkgroup,
                "subscriber_profile_version": instance.subscriber_profile_version,
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
            "collaboration_version",
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
            "collaboration_version",
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


class PlanApprovalSerializer(serializers.Serializer):
    confirm_contact_publication = serializers.BooleanField(default=False)
    publication_digest = serializers.RegexField(
        r"^[0-9a-f]{64}$",
        required=False,
        allow_blank=True,
    )


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
