from django.contrib import admin

from .models import Incident, IncidentMembership, OperationalPeriod


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ("name", "incident_number", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("name", "incident_number")


@admin.register(OperationalPeriod)
class OperationalPeriodAdmin(admin.ModelAdmin):
    list_display = ("name", "incident", "starts_at", "ends_at")
    list_filter = ("incident",)


@admin.register(IncidentMembership)
class IncidentMembershipAdmin(admin.ModelAdmin):
    list_display = ("incident", "user", "role", "is_active", "assigned_at")
    list_filter = ("role", "is_active", "incident")
    search_fields = ("user__username", "incident__name")
