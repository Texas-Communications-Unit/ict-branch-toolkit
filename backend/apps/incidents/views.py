from django.db import connection
from django.http import JsonResponse
from rest_framework import viewsets

from .models import Incident, OperationalPeriod
from .permissions import AdminWriteAuthenticatedRead
from .serializers import IncidentSerializer, OperationalPeriodSerializer


def health(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()

    payload = {"status": "ok", "database": connection.vendor}
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute("SELECT PostGIS_Version()")
            payload["postgis"] = cursor.fetchone()[0]
    return JsonResponse(payload)


class IncidentViewSet(viewsets.ModelViewSet):
    serializer_class = IncidentSerializer
    permission_classes = [AdminWriteAuthenticatedRead]

    def get_queryset(self):
        return Incident.objects.filter(archived_at__isnull=True).prefetch_related(
            "operational_periods"
        )

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class OperationalPeriodViewSet(viewsets.ModelViewSet):
    serializer_class = OperationalPeriodSerializer
    permission_classes = [AdminWriteAuthenticatedRead]

    def get_queryset(self):
        return OperationalPeriod.objects.filter(archived_at__isnull=True).select_related("incident")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
