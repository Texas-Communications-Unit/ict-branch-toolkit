from django.contrib import admin

from .models import UserRoleAssignment


@admin.register(UserRoleAssignment)
class UserRoleAssignmentAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "assigned_at", "assigned_by")
    list_filter = ("role",)
    search_fields = ("user__username", "user__email")

    def save_model(self, request, obj, form, change):
        if not obj.assigned_by_id:
            obj.assigned_by = request.user
        super().save_model(request, obj, form, change)
