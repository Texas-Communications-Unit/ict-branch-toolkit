from django.contrib import admin

from .models import ExternalIdentity, LocalContingencyAccount, UserRoleAssignment


@admin.register(UserRoleAssignment)
class UserRoleAssignmentAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "assigned_at", "assigned_by")
    list_filter = ("role",)
    search_fields = ("user__username", "user__email")

    def save_model(self, request, obj, form, change):
        if not obj.assigned_by_id:
            obj.assigned_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ExternalIdentity)
class ExternalIdentityAdmin(admin.ModelAdmin):
    list_display = (
        "provider",
        "user",
        "eligibility",
        "mapped_role",
        "last_refreshed_at",
        "valid_until",
    )
    list_filter = ("provider", "eligibility", "mapped_role")
    search_fields = ("user__username", "external_subject", "civicrm_contact_id")
    readonly_fields = [field.name for field in ExternalIdentity._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LocalContingencyAccount)
class LocalContingencyAccountAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "must_change_password",
        "created_by",
        "created_at",
        "disabled_at",
    )
    search_fields = ("user__username", "user__first_name", "reason")
    readonly_fields = [field.name for field in LocalContingencyAccount._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
