from django.contrib import admin

from .models import (
    ConventionalChannel,
    ResourceImport,
    ResourceRelease,
    ResourceSource,
    TrunkedTalkgroup,
)


@admin.register(ResourceSource)
class ResourceSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "source_type", "slug")
    search_fields = ("name", "slug")
    readonly_fields = [field.name for field in ResourceSource._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ResourceRelease)
class ResourceReleaseAdmin(admin.ModelAdmin):
    list_display = ("source", "version", "effective_status", "released_on", "imported_at")
    list_filter = ("effective_status", "source__source_type")
    readonly_fields = [field.name for field in ResourceRelease._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ConventionalChannel)
class ConventionalChannelAdmin(admin.ModelAdmin):
    list_display = ("name", "rx_frequency_hz", "tx_frequency_hz", "mode", "release")
    list_filter = ("mode", "release")
    search_fields = (
        "identifier",
        "name",
        "channel_use",
        "jurisdiction",
        "restrictions",
        "source_section",
    )
    readonly_fields = [field.name for field in ConventionalChannel._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TrunkedTalkgroup)
class TrunkedTalkgroupAdmin(admin.ModelAdmin):
    list_display = ("name", "system_name", "talkgroup_id", "release")
    list_filter = ("system_name", "release")
    search_fields = (
        "identifier",
        "name",
        "system_name",
        "restrictions",
        "source_section",
    )
    readonly_fields = [field.name for field in TrunkedTalkgroup._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ResourceImport)
class ResourceImportAdmin(admin.ModelAdmin):
    list_display = (
        "release",
        "imported_by",
        "conventional_count",
        "talkgroup_count",
        "imported_at",
    )
    readonly_fields = [field.name for field in ResourceImport._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
