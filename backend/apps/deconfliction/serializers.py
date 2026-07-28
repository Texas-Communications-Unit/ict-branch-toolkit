from rest_framework import serializers

from apps.incidents.models import Incident
from apps.plans.models import PlanRevision
from apps.resources.models import ConventionalChannel

from .models import DeconflictionAnalysis


class DeconflictionRuleSetStatusSerializer(serializers.Serializer):
    rule_set_id = serializers.CharField(read_only=True)
    rule_set_version = serializers.CharField(read_only=True)
    approved_for_operational_use = serializers.BooleanField(read_only=True)
    adjacent_channel_threshold_hz = serializers.IntegerField(read_only=True)
    rules = serializers.ListField(child=serializers.DictField(), read_only=True)
    squelch_rule = serializers.CharField(read_only=True)
    disclaimer = serializers.CharField(read_only=True)


class DeconflictionAnalysisSerializer(serializers.ModelSerializer):
    is_locked = serializers.BooleanField(read_only=True)
    revision_number = serializers.IntegerField(source="approved_revision.number", read_only=True)

    class Meta:
        model = DeconflictionAnalysis
        fields = [
            "id",
            "incident",
            "approved_revision",
            "revision_number",
            "rule_set_id",
            "rule_set_version",
            "status",
            "input_snapshot",
            "input_sha256",
            "result_snapshot",
            "result_sha256",
            "warning_count",
            "created_by",
            "approved_by",
            "approved_at",
            "created_at",
            "is_locked",
        ]
        read_only_fields = fields


class CreateDeconflictionAnalysisSerializer(serializers.Serializer):
    incident = serializers.PrimaryKeyRelatedField(
        queryset=Incident.objects.filter(archived_at__isnull=True)
    )
    approved_revision = serializers.PrimaryKeyRelatedField(
        queryset=PlanRevision.objects.select_related("plan__incident")
    )
    active_resources = serializers.PrimaryKeyRelatedField(
        queryset=ConventionalChannel.objects.select_related("release__source"),
        many=True,
        allow_empty=True,
        required=False,
    )

    def validate_active_resources(self, resources):
        if len(resources) > 500:
            raise serializers.ValidationError("Select no more than 500 active resources.")
        if len({resource.pk for resource in resources}) != len(resources):
            raise serializers.ValidationError("Each active resource may be selected once.")
        return resources
