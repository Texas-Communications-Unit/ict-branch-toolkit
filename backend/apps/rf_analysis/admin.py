from django.contrib import admin

from .models import RFAnalysisInputSnapshot, SubscriberProfile, SubscriberProfileVersion


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
