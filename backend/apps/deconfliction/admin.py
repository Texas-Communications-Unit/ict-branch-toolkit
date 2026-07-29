from django.contrib import admin

from .models import DeconflictionAnalysis, DeconflictionFindingDisposition


@admin.register(DeconflictionAnalysis)
class DeconflictionAnalysisAdmin(admin.ModelAdmin):
    list_display = (
        "incident",
        "approved_revision",
        "rule_set_version",
        "status",
        "warning_count",
        "created_at",
    )
    list_filter = ("status", "rule_set_version", "created_at")
    search_fields = ("incident__name", "rule_set_version", "input_sha256", "result_sha256")
    readonly_fields = (
        "id",
        "incident",
        "approved_revision",
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
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DeconflictionFindingDisposition)
class DeconflictionFindingDispositionAdmin(admin.ModelAdmin):
    list_display = (
        "analysis",
        "rule_id",
        "disposition",
        "created_by",
        "created_at",
    )
    list_filter = ("rule_id", "disposition", "created_at")
    search_fields = ("analysis__incident__name", "finding_key", "explanation")
    readonly_fields = (
        "id",
        "analysis",
        "finding_key",
        "rule_id",
        "disposition",
        "explanation",
        "created_by",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
