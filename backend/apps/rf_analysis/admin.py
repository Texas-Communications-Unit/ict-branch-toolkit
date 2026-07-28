from django.contrib import admin

from .models import (
    CoverageEstimate,
    DirectionalCoverageAnalysis,
    ElevationSnapshot,
    HAATCalculation,
    RFAnalysisInputSnapshot,
    SubscriberProfile,
    SubscriberProfileVersion,
)


class ReadOnlyRFAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SubscriberProfile)
class SubscriberProfileAdmin(ReadOnlyRFAdmin):
    list_display = ("name", "profile_type", "incident", "created_by", "archived_at")
    list_filter = ("profile_type", "archived_at")
    search_fields = ("name", "incident__name", "incident__incident_number")


@admin.register(SubscriberProfileVersion)
class SubscriberProfileVersionAdmin(ReadOnlyRFAdmin):
    list_display = ("profile", "number", "status", "created_by", "approved_at")
    list_filter = ("status", "erp_source", "frequency_band", "input_basis")
    search_fields = ("profile__name", "profile__incident__name", "input_sha256")


@admin.register(RFAnalysisInputSnapshot)
class RFAnalysisInputSnapshotAdmin(ReadOnlyRFAdmin):
    list_display = ("label", "incident", "profile_version", "created_by", "created_at")
    list_filter = ("archived_at",)
    search_fields = ("label", "incident__name", "input_sha256")


@admin.register(ElevationSnapshot)
class ElevationSnapshotAdmin(ReadOnlyRFAdmin):
    list_display = (
        "site",
        "provider",
        "dataset_product",
        "acquisition_state",
        "retrieved_at",
        "stale_at",
    )
    list_filter = ("provider", "acquisition_state")
    search_fields = ("site__name", "incident__name", "query_sha256", "sample_sha256")


@admin.register(HAATCalculation)
class HAATCalculationAdmin(ReadOnlyRFAdmin):
    list_display = (
        "site",
        "rf_input_snapshot",
        "profile_version",
        "calculation_state",
        "status",
        "haat_m",
        "created_at",
    )
    list_filter = ("calculation_state", "status", "method_version")
    search_fields = ("site__name", "profile_version__profile__name", "result_sha256")


@admin.register(CoverageEstimate)
class CoverageEstimateAdmin(ReadOnlyRFAdmin):
    list_display = (
        "site",
        "environment",
        "band",
        "engine_version",
        "calculation_state",
        "status",
        "nominal_distance_m",
        "created_at",
    )
    list_filter = ("environment", "band", "calculation_state", "status", "engine_version")
    search_fields = ("site__name", "rf_input_snapshot__label", "result_sha256")


@admin.register(DirectionalCoverageAnalysis)
class DirectionalCoverageAnalysisAdmin(ReadOnlyRFAdmin):
    list_display = (
        "site",
        "environment",
        "rule_version",
        "calculation_state",
        "limiting_path",
        "status",
        "probable_two_way_distance_m",
        "created_at",
    )
    list_filter = (
        "environment",
        "calculation_state",
        "limiting_path",
        "status",
        "rule_version",
    )
    search_fields = (
        "site__name",
        "infrastructure_rf_input_snapshot__label",
        "subscriber_rf_input_snapshot__label",
        "result_sha256",
    )
