from django.contrib import admin

from .models import Incident, OperationalPeriod


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ("name", "incident_number", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("name", "incident_number")


@admin.register(OperationalPeriod)
class OperationalPeriodAdmin(admin.ModelAdmin):
    list_display = ("name", "incident", "starts_at", "ends_at")
    list_filter = ("incident",)
