import hashlib

from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.policy import PLAN_EXPORT, SITE_EXPORT, user_has_permission
from apps.plans.models import PlanRevision

from .models import AuditEvent
from .serializers import ExportDigestVerificationRequestSerializer

PDF_FORMAT = "pdf"
SITE_FORMATS = ("map", "kml", "geojson", "csv")


def _action_and_permission_for_format(export_format: str):
    if export_format == PDF_FORMAT:
        return "plan_revision.pdf_exported", PLAN_EXPORT
    if export_format in SITE_FORMATS:
        return f"site_export.{export_format}", SITE_EXPORT
    raise ValidationError({"format": "Choose pdf, map, kml, geojson, or csv."})


class ExportDigestVerificationView(APIView):
    """Let anyone who could have produced an export confirm a file's digest against the audit log.

    Verification reuses the same permission required to produce the export in the first place
    (``plan.export`` for PDFs, ``site.export`` for spatial formats) rather than ``audit.view``, so
    this is genuinely self-service for operators who can already export, not admin-only.
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser]

    @extend_schema(
        request=ExportDigestVerificationRequestSerializer,
        responses={200: OpenApiTypes.OBJECT},
    )
    def post(self, request, revision_id, export_format):
        revision = get_object_or_404(
            PlanRevision.objects.select_related("plan__incident"), pk=revision_id
        )
        action, required_permission = _action_and_permission_for_format(export_format)
        if not user_has_permission(request.user, required_permission, revision.plan.incident):
            raise PermissionDenied("Your incident role cannot verify this export.")

        content_sha256 = request.data.get("content_sha256")
        uploaded_file = request.data.get("file")
        if uploaded_file is not None:
            hasher = hashlib.sha256()
            for chunk in uploaded_file.chunks():
                hasher.update(chunk)
            content_sha256 = hasher.hexdigest()
        if not content_sha256:
            raise ValidationError(
                {"content_sha256": "Provide a content_sha256 hex digest or a file to hash."}
            )
        content_sha256 = content_sha256.strip().lower()

        target_type = revision._meta.label_lower
        matches = AuditEvent.objects.filter(
            action=action,
            target_type=target_type,
            target_id=str(revision.pk),
            details__content_sha256=content_sha256,
        ).order_by("sequence")
        event = matches.first()

        if event is None:
            return Response(
                {
                    "verified": False,
                    "detail": (
                        "No export audit event matches this digest for the given "
                        "revision and format."
                    ),
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "verified": True,
                "audit_event_id": str(event.id),
                "occurred_at": event.occurred_at,
                "actor_id": event.actor_id,
                "action": event.action,
                "byte_size": event.details.get("byte_size"),
                "revision_number": event.details.get("revision_number"),
                "revision_status": event.details.get("revision_status"),
            },
            status=status.HTTP_200_OK,
        )
