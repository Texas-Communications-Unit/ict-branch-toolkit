from django.urls import path

from .views import ExportDigestVerificationView

urlpatterns = [
    path(
        "audit/revisions/<uuid:revision_id>/exports/<str:export_format>/verify/",
        ExportDigestVerificationView.as_view(),
        name="export-digest-verify",
    ),
]
