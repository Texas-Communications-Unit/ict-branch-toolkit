from rest_framework import serializers

from apps.incidents.models import Incident
from apps.plans.models import PlanRevision

from .models import DeconflictionAnalysis, DeconflictionFindingDisposition


class DeconflictionRuleSetStatusSerializer(serializers.Serializer):
    rule_set_id = serializers.CharField(read_only=True)
    rule_set_version = serializers.CharField(read_only=True)
    approved_for_operational_use = serializers.BooleanField(read_only=True)
    close_frequency_threshold_hz = serializers.IntegerField(read_only=True)
    rules = serializers.ListField(child=serializers.DictField(), read_only=True)
    analysis_statuses = serializers.ListField(
        child=serializers.DictField(),
        read_only=True,
    )
    access_code_source_hierarchy = serializers.ListField(
        child=serializers.CharField(),
        read_only=True,
    )
    squelch_rule = serializers.CharField(read_only=True)
    disclaimer = serializers.CharField(read_only=True)


class DeconflictionFindingDispositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeconflictionFindingDisposition
        fields = [
            "id",
            "analysis",
            "finding_key",
            "rule_id",
            "disposition",
            "explanation",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields


class CreateDeconflictionFindingDispositionSerializer(serializers.Serializer):
    finding_key = serializers.RegexField(r"^[0-9a-f]{64}$")
    disposition = serializers.ChoiceField(
        choices=DeconflictionFindingDisposition.Disposition.choices
    )
    explanation = serializers.CharField(max_length=1000, trim_whitespace=True)

    def validate_explanation(self, value):
        if not value:
            raise serializers.ValidationError(
                "Explain the practitioner disposition or required follow-up."
            )
        return value


class DeconflictionAnalysisSerializer(serializers.ModelSerializer):
    is_locked = serializers.BooleanField(read_only=True)
    revision_number = serializers.IntegerField(source="approved_revision.number", read_only=True)
    finding_dispositions = DeconflictionFindingDispositionSerializer(
        many=True,
        read_only=True,
    )

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
            "finding_dispositions",
        ]
        read_only_fields = fields


class CreateDeconflictionAnalysisSerializer(serializers.Serializer):
    incident = serializers.PrimaryKeyRelatedField(
        queryset=Incident.objects.filter(archived_at__isnull=True)
    )
    approved_revision = serializers.PrimaryKeyRelatedField(
        queryset=PlanRevision.objects.select_related("plan__incident")
    )
