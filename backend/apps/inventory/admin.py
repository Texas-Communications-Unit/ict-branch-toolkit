from django.contrib import admin

from .models import (
    Asset,
    AssetAttachment,
    AssetCheckout,
    AssetImportBatch,
    ChargingRecord,
    MaintenanceRecord,
    ProgrammingRecord,
)


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ("asset_id", "category", "manufacturer", "model", "status", "parent")
    search_fields = ("asset_id", "serial_number", "alias", "manufacturer", "model")
    list_filter = ("category", "status")


@admin.register(AssetCheckout)
class AssetCheckoutAdmin(admin.ModelAdmin):
    list_display = ("asset", "incident", "assigned_name", "state", "checked_out_at")
    exclude = ("driver_license_ciphertext",)
    readonly_fields = ("driver_license_last_four",)


@admin.register(ProgrammingRecord)
class ProgrammingRecordAdmin(admin.ModelAdmin):
    list_display = (
        "asset",
        "template_name",
        "template_version",
        "programmed_at",
        "codeplug_backup_saved",
    )


admin.site.register(MaintenanceRecord)
admin.site.register(ChargingRecord)
admin.site.register(AssetAttachment)
admin.site.register(AssetImportBatch)
