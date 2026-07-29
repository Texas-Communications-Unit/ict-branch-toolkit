from django.contrib import admin

from .models import (
    CollaborationChange,
    CollaborationResolution,
    PresenceLease,
    SensitiveFieldRule,
)


class RetainedReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CollaborationChange)
class CollaborationChangeAdmin(RetainedReadOnlyAdmin):
    list_display = ("id", "incident", "operation", "disposition", "actor", "created_at")
    list_filter = ("operation", "disposition")
    search_fields = ("id", "client_mutation_id", "object_id")


@admin.register(CollaborationResolution)
class CollaborationResolutionAdmin(RetainedReadOnlyAdmin):
    list_display = ("id", "conflict", "decision", "resolved_by", "created_at")
    list_filter = ("decision",)


@admin.register(SensitiveFieldRule)
class SensitiveFieldRuleAdmin(RetainedReadOnlyAdmin):
    list_display = (
        "incident",
        "field_name",
        "unauthorized_visibility",
        "version",
        "updated_at",
    )
    list_filter = ("field_name", "unauthorized_visibility", "log_reads")


@admin.register(PresenceLease)
class PresenceLeaseAdmin(RetainedReadOnlyAdmin):
    list_display = ("user", "incident", "revision", "section", "mode", "expires_at")
    list_filter = ("mode", "section")
