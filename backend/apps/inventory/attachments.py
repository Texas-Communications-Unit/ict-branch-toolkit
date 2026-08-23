import io
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from PIL import Image, UnidentifiedImageError

from apps.audit.services import record_event

from .models import AssetAttachment

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".csv", ".jpg", ".jpeg", ".png", ".webp", ".docx", ".xlsx"}
IMAGE_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
OFFICE_MARKERS = {
    ".docx": "word/document.xml",
    ".xlsx": "xl/workbook.xml",
}


def _validate_zip_document(content, extension):
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        raise ValidationError("The Office document is not a valid ZIP-based file.") from None
    with archive:
        members = archive.infolist()
        if len(members) > 200 or sum(member.file_size for member in members) > 50 * 1024 * 1024:
            raise ValidationError("The expanded Office document exceeds safety limits.")
        if OFFICE_MARKERS[extension] not in {member.filename for member in members}:
            raise ValidationError(f"The uploaded file is not a valid {extension} document.")


def validate_attachment(uploaded_file):
    original_name = Path(uploaded_file.name).name
    if not original_name or len(original_name) > 255:
        raise ValidationError("The attachment filename is invalid or exceeds 255 characters.")
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            "Allowed attachment types: PDF, TXT, CSV, JPG, PNG, WEBP, DOCX, and XLSX."
        )
    maximum = settings.ICT_ATTACHMENT_MAX_BYTES
    content = uploaded_file.read(maximum + 1)
    if not content:
        raise ValidationError("The attachment is empty.")
    if len(content) > maximum:
        raise ValidationError(f"The attachment exceeds the {maximum // (1024 * 1024)} MiB limit.")

    if extension == ".pdf":
        if not content.startswith(b"%PDF-") or b"%%EOF" not in content[-2048:]:
            raise ValidationError("The uploaded file is not a valid PDF.")
        content_type = "application/pdf"
    elif extension in {".txt", ".csv"}:
        try:
            content.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise ValidationError("Text and CSV attachments must use UTF-8 encoding.") from None
        if b"\x00" in content:
            raise ValidationError("The text attachment contains invalid null characters.")
        content_type = "text/csv" if extension == ".csv" else "text/plain"
    elif extension in IMAGE_TYPES:
        try:
            with Image.open(io.BytesIO(content)) as image:
                image.verify()
                detected_format = image.format
        except (UnidentifiedImageError, OSError):
            raise ValidationError("The uploaded file is not a valid image.") from None
        expected_formats = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}
        if detected_format != expected_formats[extension]:
            raise ValidationError("The image content does not match its filename extension.")
        content_type = IMAGE_TYPES[extension]
    else:
        _validate_zip_document(content, extension)
        content_type = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if extension == ".docx"
            else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    return original_name, content_type, content


@transaction.atomic
def create_attachment(*, asset, uploaded_file, description, actor):
    original_name, content_type, content = validate_attachment(uploaded_file)
    attachment = AssetAttachment(
        asset=asset,
        original_name=original_name,
        content_type=content_type,
        size_bytes=len(content),
        description=description,
        uploaded_by=actor,
    )
    try:
        attachment.file.save(original_name, ContentFile(content), save=False)
        attachment.save()
        record_event(
            actor=actor,
            action="inventory.asset_attachment_uploaded",
            target=attachment,
            details={
                "asset_id": asset.asset_id,
                "attachment_id": str(attachment.id),
                "content_type": content_type,
                "size_bytes": len(content),
            },
        )
    except Exception:
        if attachment.file.name:
            try:
                attachment.file.storage.delete(attachment.file.name)
            except OSError:
                pass
        raise
    return attachment


@transaction.atomic
def delete_attachment(*, attachment, actor):
    storage = attachment.file.storage
    stored_name = attachment.file.name
    attachment.deleted_by = actor
    attachment.deleted_at = timezone.now()
    attachment.save(update_fields=["deleted_by", "deleted_at"])
    file_delete_failed = False
    try:
        if stored_name:
            storage.delete(stored_name)
    except OSError:
        file_delete_failed = True
    record_event(
        actor=actor,
        action="inventory.asset_attachment_deleted",
        target=attachment,
        details={
            "asset_id": attachment.asset.asset_id,
            "attachment_id": str(attachment.id),
            "original_name": attachment.original_name,
            "file_delete_failed": file_delete_failed,
        },
    )
    return attachment
