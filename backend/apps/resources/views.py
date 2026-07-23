from drf_spectacular.utils import extend_schema
from rest_framework import generics, status, viewsets
from rest_framework.response import Response

from apps.accounts.permissions import LibraryImportPermission, PolicyPermission
from apps.accounts.policy import LIBRARY_VIEW

from .models import ConventionalChannel, ResourceRelease, TrunkedTalkgroup
from .serializers import (
    ChannelImportResponseSerializer,
    ChannelImportSerializer,
    ConventionalChannelSerializer,
    ResourceReleaseSerializer,
    TrunkedTalkgroupSerializer,
)
from .services import ReferenceApprovalRequired, apply_import, preview_import


class LibraryReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [PolicyPermission]
    policy_actions = {"list": LIBRARY_VIEW, "retrieve": LIBRARY_VIEW}


class ResourceReleaseViewSet(LibraryReadOnlyViewSet):
    queryset = ResourceRelease.objects.select_related("source", "imported_by")
    serializer_class = ResourceReleaseSerializer


class ConventionalChannelViewSet(LibraryReadOnlyViewSet):
    queryset = ConventionalChannel.objects.select_related("release__source")
    serializer_class = ConventionalChannelSerializer


class TrunkedTalkgroupViewSet(LibraryReadOnlyViewSet):
    queryset = TrunkedTalkgroup.objects.select_related("release__source")
    serializer_class = TrunkedTalkgroupSerializer


def structured_errors(errors, prefix=""):
    output = []
    if isinstance(errors, dict):
        for key, value in errors.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            output.extend(structured_errors(value, path))
    elif isinstance(errors, list):
        for index, value in enumerate(errors):
            path = f"{prefix}.{index}" if not isinstance(value, str) else prefix
            output.extend(structured_errors(value, path))
    else:
        output.append(
            {
                "path": prefix or "non_field_errors",
                "code": getattr(errors, "code", "invalid"),
                "message": str(errors),
            }
        )
    return output


class ChannelImportView(generics.GenericAPIView):
    permission_classes = [LibraryImportPermission]
    serializer_class = ChannelImportSerializer

    @extend_schema(
        request=ChannelImportSerializer,
        responses={
            200: ChannelImportResponseSerializer,
            201: ChannelImportResponseSerializer,
            400: ChannelImportResponseSerializer,
            403: ChannelImportResponseSerializer,
        },
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "valid": False,
                    "dry_run": bool(request.data.get("dry_run", True)),
                    "errors": structured_errors(serializer.errors),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if serializer.validated_data["dry_run"]:
            preview = preview_import(serializer.validated_data)
            return Response(preview, status=status.HTTP_200_OK)
        try:
            record = apply_import(
                validated_data=serializer.validated_data,
                raw_payload=request.data,
                actor=request.user,
            )
        except ReferenceApprovalRequired as error:
            return Response(
                {
                    "valid": False,
                    "dry_run": False,
                    "errors": structured_errors(error.detail, "approval"),
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(
            {
                "valid": True,
                "dry_run": False,
                "import_id": record.id,
                "release_id": record.release_id,
                "created": {
                    "conventional_channels": record.conventional_count,
                    "trunked_talkgroups": record.talkgroup_count,
                },
                "errors": [],
            },
            status=status.HTTP_201_CREATED,
        )
