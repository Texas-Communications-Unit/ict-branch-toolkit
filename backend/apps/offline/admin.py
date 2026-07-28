from django.contrib import admin

from .models import OfflineConflictResolution, OfflineMutationReceipt, OfflinePackage


class RetainedReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(OfflinePackage)
class OfflinePackageAdmin(RetainedReadOnlyAdmin):
    list_display = (
        "id",
        "incident",
        "requested_by",
        "device_id",
        "status",
        "expires_at",
        "created_at",
    )
    list_filter = ("status",)


@admin.register(OfflineMutationReceipt)
class OfflineMutationReceiptAdmin(RetainedReadOnlyAdmin):
    list_display = (
        "id",
        "package",
        "sequence",
        "operation",
        "status",
        "received_at",
    )
    list_filter = ("status", "operation")


@admin.register(OfflineConflictResolution)
class OfflineConflictResolutionAdmin(RetainedReadOnlyAdmin):
    list_display = ("id", "receipt", "decision", "resolved_by", "created_at")
    list_filter = ("decision",)
