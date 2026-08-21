from django.db.models import Count, Q
from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination

from apps.accounts.permissions import PolicyPermission
from apps.accounts.policy import LIBRARY_VIEW

from .models import AntennaStructure, UlsLicense
from .serializers import AntennaStructureSerializer, UlsLicenseSerializer


class FccSearchPagination(PageNumberPagination):
    page_size = 50
    max_page_size = 100
    page_size_query_param = "page_size"


class FccReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [PolicyPermission]
    policy_actions = {"list": LIBRARY_VIEW, "retrieve": LIBRARY_VIEW}
    pagination_class = FccSearchPagination


class AntennaStructureViewSet(FccReadOnlyViewSet):
    serializer_class = AntennaStructureSerializer

    def get_queryset(self):
        queryset = AntennaStructure.objects.select_related("batch").filter(batch__is_current=True)
        search = self.request.query_params.get("search", "").strip()
        status_code = self.request.query_params.get("status", "").strip()
        if search:
            queryset = queryset.filter(
                Q(registration_number__icontains=search)
                | Q(owner_name__icontains=search)
                | Q(owner_frn__icontains=search)
                | Q(faa_study_number__icontains=search)
                | Q(structure_type__icontains=search)
            )
        if status_code:
            queryset = queryset.filter(status_code__iexact=status_code)
        return queryset


class UlsLicenseViewSet(FccReadOnlyViewSet):
    serializer_class = UlsLicenseSerializer

    def get_queryset(self):
        queryset = (
            UlsLicense.objects.select_related("batch")
            .filter(batch__is_current=True)
            .annotate(
                location_count=Count("locations", distinct=True),
                frequency_count=Count("frequencies", distinct=True),
            )
        )
        search = self.request.query_params.get("search", "").strip()
        state = self.request.query_params.get("state", "").strip()
        service = self.request.query_params.get("service_code", "").strip()
        status_code = self.request.query_params.get("status", "").strip()
        if search:
            queryset = queryset.filter(
                Q(call_sign__icontains=search)
                | Q(licensee_name__icontains=search)
                | Q(frn__icontains=search)
                | Q(city__icontains=search)
            )
        if state:
            queryset = queryset.filter(state__iexact=state)
        if service:
            queryset = queryset.filter(radio_service_code__iexact=service)
        if status_code:
            queryset = queryset.filter(license_status__iexact=status_code)
        return queryset
