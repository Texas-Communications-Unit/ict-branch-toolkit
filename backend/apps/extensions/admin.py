from django.contrib import admin

from .models import ExtensionExecution, ExtensionInstallation


@admin.register(ExtensionInstallation)
class ExtensionInstallationAdmin(admin.ModelAdmin):
    list_display = (
        "extension_key",
        "extension_version",
        "contract_version",
        "enabled",
        "installed_at",
        "updated_at",
    )
    list_filter = ("enabled", "contract_version")
    search_fields = ("extension_key", "extension_version", "manifest_sha256")
    readonly_fields = (
        "id",
        "extension_key",
        "extension_version",
        "contract_version",
        "manifest_snapshot",
        "manifest_sha256",
        "enabled",
        "installed_by",
        "installed_at",
        "updated_by",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ExtensionExecution)
class ExtensionExecutionAdmin(admin.ModelAdmin):
    list_display = (
        "extension_key",
        "capability",
        "incident",
        "source_revision",
        "status",
        "created_at",
    )
    list_filter = ("status", "capability_kind", "output_classification", "created_at")
    search_fields = (
        "extension_key",
        "capability",
        "incident__name",
        "input_sha256",
        "result_sha256",
    )
    readonly_fields = (
        "id",
        "installation",
        "extension_key",
        "extension_version",
        "contract_version",
        "capability",
        "capability_kind",
        "incident",
        "source_revision",
        "input_snapshot",
        "input_sha256",
        "result_snapshot",
        "result_sha256",
        "output_classification",
        "status",
        "failure_code",
        "failure_message",
        "created_by",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
