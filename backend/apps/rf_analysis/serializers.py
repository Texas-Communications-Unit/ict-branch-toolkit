from decimal import Decimal

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.incidents.models import Incident
from apps.plans.models import PlanRevision
from apps.sites.models import RadioSite

from .models import (
    CalibrationSet,
    CoverageEstimate,
    DirectionalCoverageAnalysis,
    ElevationSnapshot,
    FieldObservation,
    FieldObservationReview,
    HAATCalculation,
    Phase2ValidationBundle,
    RFAnalysisInputSnapshot,
    SubscriberProfile,
    SubscriberProfileVersion,
)
from .phase2_validation import stale_reasons
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
    profile_name = serializers.CharField(source="profile_version.profile.name", read_only=True)
    profile_type = serializers.CharField(
        source="profile_version.profile.profile_type",
        read_only=True,
    )
    profile_version_number = serializers.IntegerField(
        source="profile_version.number",
        read_only=True,
    )

    class Meta:
        model = RFAnalysisInputSnapshot
        fields = [
            "id",
            "incident",
            "profile_version",
            "profile_name",
            "profile_type",
            "profile_version_number",
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


class ElevationSnapshotSummarySerializer(serializers.ModelSerializer):
    current_state = serializers.CharField(read_only=True)

    class Meta:
        model = ElevationSnapshot
        fields = [
            "id",
            "incident",
            "site",
            "query_sha256",
            "provider",
            "dataset_product",
            "horizontal_crs",
            "vertical_crs",
            "target_vertical_crs",
            "resolution_m",
            "source_version",
            "source_retrieved_at",
            "license_terms_url",
            "permitted_use",
            "coverage",
            "source_content_sha256",
            "acquisition_state",
            "current_state",
            "sample_sha256",
            "transformation",
            "warnings",
            "retrieved_at",
            "stale_at",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields


class ElevationSnapshotSerializer(ElevationSnapshotSummarySerializer):
    class Meta(ElevationSnapshotSummarySerializer.Meta):
        fields = [
            *ElevationSnapshotSummarySerializer.Meta.fields,
            "query_snapshot",
            "sample_snapshot",
        ]
        read_only_fields = fields


class HAATCalculationSerializer(serializers.ModelSerializer):
    is_locked = serializers.BooleanField(read_only=True)
    elevation = ElevationSnapshotSummarySerializer(source="elevation_snapshot", read_only=True)
    site_name = serializers.CharField(source="site.name", read_only=True)
    profile_name = serializers.CharField(source="profile_version.profile.name", read_only=True)
    profile_version_number = serializers.IntegerField(
        source="profile_version.number",
        read_only=True,
    )
    rf_input_label = serializers.CharField(source="rf_input_snapshot.label", read_only=True)

    class Meta:
        model = HAATCalculation
        fields = [
            "id",
            "incident",
            "site",
            "site_name",
            "profile_version",
            "profile_name",
            "profile_version_number",
            "rf_input_snapshot",
            "rf_input_label",
            "elevation_snapshot",
            "elevation",
            "supersedes",
            "status",
            "calculation_state",
            "method",
            "method_version",
            "radial_count",
            "start_azimuth_deg",
            "sampling_interval_m",
            "inner_distance_m",
            "outer_distance_m",
            "rounding_m",
            "antenna_agl_m",
            "site_elevation_m",
            "antenna_amsl_m",
            "average_terrain_m",
            "haat_m",
            "sample_count",
            "excluded_sample_count",
            "algorithm_snapshot",
            "exclusions",
            "warnings",
            "result_snapshot",
            "result_sha256",
            "created_by",
            "approved_by",
            "approved_at",
            "created_at",
            "is_locked",
        ]
        read_only_fields = fields


class CreateHAATCalculationSerializer(serializers.Serializer):
    site = serializers.PrimaryKeyRelatedField(queryset=RadioSite.objects.all())
    rf_input_snapshot = serializers.PrimaryKeyRelatedField(
        queryset=RFAnalysisInputSnapshot.objects.select_related(
            "incident",
            "profile_version__profile",
        )
    )
    radial_count = serializers.IntegerField(default=8, min_value=4, max_value=360)
    start_azimuth_deg = serializers.DecimalField(
        default=Decimal("0"),
        max_digits=6,
        decimal_places=3,
        min_value=Decimal("0"),
        max_value=Decimal("359.999"),
    )
    sampling_interval_m = serializers.IntegerField(
        default=1000,
        min_value=10,
        max_value=100_000,
    )
    inner_distance_m = serializers.IntegerField(
        default=3000,
        min_value=1,
        max_value=100_000,
    )
    outer_distance_m = serializers.IntegerField(
        default=16_000,
        min_value=1,
        max_value=100_000,
    )
    rounding_m = serializers.DecimalField(
        default=Decimal("0.1"),
        max_digits=7,
        decimal_places=3,
        min_value=Decimal("0.001"),
        max_value=Decimal("100"),
    )
    force_refresh = serializers.BooleanField(default=False)

    def validate(self, attrs):
        if attrs["site"].incident_id != attrs["rf_input_snapshot"].incident_id:
            raise serializers.ValidationError(
                "Site and RF analysis input snapshot must belong to the same incident."
            )
        if attrs["outer_distance_m"] <= attrs["inner_distance_m"]:
            raise serializers.ValidationError(
                {"outer_distance_m": "Outer distance must be greater than inner distance."}
            )
        return attrs


class CoverageEstimateSerializer(serializers.ModelSerializer):
    is_locked = serializers.BooleanField(read_only=True)
    site_name = serializers.CharField(source="site.name", read_only=True)
    rf_input_label = serializers.CharField(source="rf_input_snapshot.label", read_only=True)
    haat_result_sha256 = serializers.CharField(
        source="haat_calculation.result_sha256",
        read_only=True,
    )

    class Meta:
        model = CoverageEstimate
        fields = [
            "id",
            "incident",
            "site",
            "site_name",
            "rf_input_snapshot",
            "rf_input_label",
            "haat_calculation",
            "haat_result_sha256",
            "status",
            "calculation_state",
            "environment",
            "band",
            "engine",
            "engine_version",
            "preset",
            "preset_version",
            "center_latitude",
            "center_longitude",
            "nominal_distance_m",
            "conservative_distance_m",
            "optimistic_distance_m",
            "input_snapshot",
            "input_sha256",
            "model_snapshot",
            "warnings",
            "exclusions",
            "explanation",
            "result_snapshot",
            "result_sha256",
            "created_by",
            "approved_by",
            "approved_at",
            "created_at",
            "is_locked",
        ]
        read_only_fields = fields


class CreateCoverageEstimateSerializer(serializers.Serializer):
    haat_calculation = serializers.PrimaryKeyRelatedField(
        queryset=HAATCalculation.objects.select_related(
            "incident",
            "site",
            "rf_input_snapshot",
        )
    )
    environment = serializers.ChoiceField(choices=CoverageEstimate.Environment.choices)
    preset = serializers.CharField(
        max_length=80,
        default="balanced",
        allow_blank=False,
        trim_whitespace=True,
    )


class DirectionalCoverageAnalysisSerializer(serializers.ModelSerializer):
    is_locked = serializers.BooleanField(read_only=True)
    site_name = serializers.CharField(source="site.name", read_only=True)
    infrastructure_label = serializers.CharField(
        source="infrastructure_rf_input_snapshot.label",
        read_only=True,
    )
    subscriber_label = serializers.CharField(
        source="subscriber_rf_input_snapshot.label",
        read_only=True,
    )
    subscriber_profile_name = serializers.CharField(
        source="subscriber_rf_input_snapshot.profile_version.profile.name",
        read_only=True,
    )
    subscriber_profile_type = serializers.CharField(
        source="subscriber_rf_input_snapshot.profile_version.profile.profile_type",
        read_only=True,
    )
    haat_result_sha256 = serializers.CharField(
        source="haat_calculation.result_sha256",
        read_only=True,
    )

    class Meta:
        model = DirectionalCoverageAnalysis
        fields = [
            "id",
            "incident",
            "site",
            "site_name",
            "infrastructure_rf_input_snapshot",
            "infrastructure_label",
            "subscriber_rf_input_snapshot",
            "subscriber_label",
            "subscriber_profile_name",
            "subscriber_profile_type",
            "haat_calculation",
            "haat_result_sha256",
            "status",
            "calculation_state",
            "environment",
            "engine",
            "engine_version",
            "preset",
            "preset_version",
            "rule_version",
            "center_latitude",
            "center_longitude",
            "talk_out_distance_m",
            "talk_in_distance_m",
            "probable_two_way_distance_m",
            "limiting_path",
            "input_snapshot",
            "input_sha256",
            "model_snapshot",
            "warnings",
            "exclusions",
            "explanation",
            "result_snapshot",
            "result_sha256",
            "created_by",
            "approved_by",
            "approved_at",
            "created_at",
            "is_locked",
        ]
        read_only_fields = fields


class CreateDirectionalCoverageAnalysisSerializer(serializers.Serializer):
    haat_calculation = serializers.PrimaryKeyRelatedField(
        queryset=HAATCalculation.objects.select_related(
            "incident",
            "site",
            "rf_input_snapshot",
        )
    )
    subscriber_rf_input_snapshot = serializers.PrimaryKeyRelatedField(
        queryset=RFAnalysisInputSnapshot.objects.select_related(
            "incident",
            "profile_version__profile",
        )
    )
    environment = serializers.ChoiceField(choices=CoverageEstimate.Environment.choices)
    preset = serializers.CharField(
        max_length=80,
        default="balanced",
        allow_blank=False,
        trim_whitespace=True,
    )

    def validate(self, attrs):
        if (
            attrs["haat_calculation"].incident_id
            != attrs["subscriber_rf_input_snapshot"].incident_id
        ):
            raise serializers.ValidationError(
                "HAAT and subscriber RF snapshots must belong to the same incident."
            )
        return attrs


class FieldObservationReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = FieldObservationReview
        fields = [
            "id",
            "observation",
            "decision",
            "reason",
            "evidence_sha256",
            "reviewed_by",
            "created_at",
        ]
        read_only_fields = fields


class FieldObservationSerializer(serializers.ModelSerializer):
    reviews = FieldObservationReviewSerializer(many=True, read_only=True)
    current_review_state = serializers.CharField(read_only=True)
    superseded_by = serializers.SerializerMethodField()
    infrastructure_label = serializers.CharField(
        source="infrastructure_rf_input_snapshot.label",
        read_only=True,
    )
    subscriber_label = serializers.CharField(
        source="subscriber_rf_input_snapshot.label",
        read_only=True,
    )

    class Meta:
        model = FieldObservation
        fields = [
            "id",
            "incident",
            "infrastructure_rf_input_snapshot",
            "infrastructure_label",
            "subscriber_rf_input_snapshot",
            "subscriber_label",
            "coverage_estimate",
            "directional_analysis",
            "supersedes",
            "superseded_by",
            "classification",
            "evidence_type",
            "observed_from",
            "observed_to",
            "location_precision",
            "coordinate_reference",
            "latitude",
            "longitude",
            "location_precision_m",
            "direction_degrees",
            "path_distance_m",
            "observer_source",
            "collection_method",
            "environment",
            "measurements",
            "notes",
            "quality_flags",
            "source_record_id",
            "source_revision",
            "input_snapshot",
            "input_sha256",
            "created_by",
            "created_at",
            "current_review_state",
            "reviews",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.UUIDField(allow_null=True))
    def get_superseded_by(self, obj: FieldObservation) -> str | None:
        superseding_observation = getattr(obj, "superseded_by", None)
        return str(superseding_observation.id) if superseding_observation else None


class CreateFieldObservationSerializer(serializers.Serializer):
    incident = serializers.PrimaryKeyRelatedField(queryset=Incident.objects.all())
    infrastructure_rf_input_snapshot = serializers.PrimaryKeyRelatedField(
        queryset=RFAnalysisInputSnapshot.objects.select_related("incident")
    )
    subscriber_rf_input_snapshot = serializers.PrimaryKeyRelatedField(
        queryset=RFAnalysisInputSnapshot.objects.select_related("incident")
    )
    coverage_estimate = serializers.PrimaryKeyRelatedField(
        queryset=CoverageEstimate.objects.select_related("incident", "rf_input_snapshot"),
        required=False,
        allow_null=True,
    )
    directional_analysis = serializers.PrimaryKeyRelatedField(
        queryset=DirectionalCoverageAnalysis.objects.select_related(
            "incident",
            "infrastructure_rf_input_snapshot",
            "subscriber_rf_input_snapshot",
        ),
        required=False,
        allow_null=True,
    )
    supersedes = serializers.PrimaryKeyRelatedField(
        queryset=FieldObservation.objects.select_related("incident"),
        required=False,
        allow_null=True,
    )
    classification = serializers.ChoiceField(choices=FieldObservation.Classification.choices)
    evidence_type = serializers.ChoiceField(choices=FieldObservation.EvidenceType.choices)
    observed_from = serializers.DateTimeField()
    observed_to = serializers.DateTimeField()
    location_precision = serializers.ChoiceField(choices=FieldObservation.LocationPrecision.choices)
    latitude = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        min_value=Decimal("-90"),
        max_value=Decimal("90"),
        required=False,
        allow_null=True,
    )
    longitude = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        min_value=Decimal("-180"),
        max_value=Decimal("180"),
        required=False,
        allow_null=True,
    )
    location_precision_m = serializers.IntegerField(
        min_value=1,
        max_value=1_000_000,
        required=False,
        allow_null=True,
    )
    direction_degrees = serializers.DecimalField(
        max_digits=6,
        decimal_places=3,
        min_value=Decimal("0"),
        max_value=Decimal("359.999"),
        required=False,
        allow_null=True,
    )
    path_distance_m = serializers.IntegerField(
        min_value=1,
        max_value=1_000_000,
        required=False,
        allow_null=True,
    )
    observer_source = serializers.CharField(max_length=160, trim_whitespace=True)
    collection_method = serializers.CharField(max_length=120, trim_whitespace=True)
    environment = serializers.JSONField(default=dict)
    measurements = serializers.JSONField(default=dict)
    notes = serializers.CharField(
        max_length=2_000,
        allow_blank=True,
        trim_whitespace=True,
        default="",
    )
    quality_flags = serializers.ListField(
        child=serializers.CharField(max_length=80),
        default=list,
    )
    source_record_id = serializers.CharField(
        max_length=160,
        allow_blank=True,
        trim_whitespace=True,
        default="",
    )
    source_revision = serializers.CharField(max_length=160, trim_whitespace=True)


class ReviewFieldObservationSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=FieldObservationReview.Decision.choices)
    reason = serializers.CharField(max_length=1_000, trim_whitespace=True)


class CalibrationSetSerializer(serializers.ModelSerializer):
    is_locked = serializers.BooleanField(read_only=True)
    observation_ids = serializers.SerializerMethodField()

    class Meta:
        model = CalibrationSet
        fields = [
            "id",
            "incident",
            "name",
            "version",
            "status",
            "calculation_state",
            "algorithm",
            "algorithm_version",
            "parameters",
            "baseline_preset",
            "baseline_preset_version",
            "observation_ids",
            "observation_snapshot",
            "observation_sha256",
            "recommended_preset",
            "before_after",
            "warnings",
            "exclusions",
            "result_snapshot",
            "result_sha256",
            "created_by",
            "approved_by",
            "approved_at",
            "created_at",
            "is_locked",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.ListField(child=serializers.UUIDField()))
    def get_observation_ids(self, obj: CalibrationSet) -> list[str]:
        return [str(value) for value in obj.observations.values_list("id", flat=True)]


class CreateCalibrationSetSerializer(serializers.Serializer):
    incident = serializers.PrimaryKeyRelatedField(queryset=Incident.objects.all())
    name = serializers.CharField(max_length=160, trim_whitespace=True)
    observations = serializers.PrimaryKeyRelatedField(
        queryset=FieldObservation.objects.select_related("incident"),
        many=True,
    )
    baseline_preset = serializers.CharField(max_length=80, trim_whitespace=True)
    baseline_preset_version = serializers.CharField(max_length=80, trim_whitespace=True)
    parameters = serializers.JSONField(default=dict)


class Phase2ValidationBundleSerializer(serializers.ModelSerializer):
    is_locked = serializers.BooleanField(read_only=True)
    is_stale = serializers.SerializerMethodField()
    stale_reasons = serializers.SerializerMethodField()
    approval_eligible = serializers.SerializerMethodField()

    class Meta:
        model = Phase2ValidationBundle
        fields = [
            "id",
            "incident",
            "approved_revision",
            "haat_calculation",
            "coverage_estimate",
            "directional_analysis",
            "calibration_set",
            "supersedes",
            "validation_profile_id",
            "validation_profile_version",
            "app_version",
            "job_state",
            "progress_step",
            "progress_percent",
            "status",
            "input_snapshot",
            "input_sha256",
            "result_snapshot",
            "result_sha256",
            "failure_code",
            "failure_message",
            "created_by",
            "approved_by",
            "created_at",
            "started_at",
            "completed_at",
            "approved_at",
            "updated_at",
            "is_locked",
            "is_stale",
            "stale_reasons",
            "approval_eligible",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.BooleanField())
    def get_is_stale(self, obj: Phase2ValidationBundle) -> bool:
        return bool(stale_reasons(obj))

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_stale_reasons(self, obj: Phase2ValidationBundle) -> list[str]:
        return stale_reasons(obj)

    @extend_schema_field(serializers.BooleanField())
    def get_approval_eligible(self, obj: Phase2ValidationBundle) -> bool:
        from django.conf import settings

        return (
            obj.job_state == Phase2ValidationBundle.JobState.COMPLETE
            and obj.status == Phase2ValidationBundle.Status.DRAFT
            and not stale_reasons(obj)
            and obj.validation_profile_version
            in getattr(settings, "ICT_APPROVED_PHASE2_VALIDATION_PROFILES", [])
        )


class CreatePhase2ValidationBundleSerializer(serializers.Serializer):
    incident = serializers.PrimaryKeyRelatedField(queryset=Incident.objects.all())
    approved_revision = serializers.PrimaryKeyRelatedField(
        queryset=PlanRevision.objects.select_related("plan__incident", "plan__operational_period")
    )
    haat_calculation = serializers.PrimaryKeyRelatedField(
        queryset=HAATCalculation.objects.select_related(
            "incident",
            "elevation_snapshot",
            "rf_input_snapshot",
        )
    )
    coverage_estimate = serializers.PrimaryKeyRelatedField(
        queryset=CoverageEstimate.objects.select_related(
            "incident",
            "haat_calculation",
            "rf_input_snapshot",
        )
    )
    directional_analysis = serializers.PrimaryKeyRelatedField(
        queryset=DirectionalCoverageAnalysis.objects.select_related(
            "incident",
            "haat_calculation",
            "infrastructure_rf_input_snapshot",
            "subscriber_rf_input_snapshot",
        )
    )
    calibration_set = serializers.PrimaryKeyRelatedField(
        queryset=CalibrationSet.objects.select_related("incident")
    )
    supersedes = serializers.PrimaryKeyRelatedField(
        queryset=Phase2ValidationBundle.objects.all(),
        required=False,
        allow_null=True,
    )
