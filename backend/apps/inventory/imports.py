import csv
import hashlib
import io
import re
import zipfile
from datetime import date
from pathlib import Path
from xml.etree import ElementTree

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.audit.services import record_event

from .models import Asset, AssetImportBatch

MAX_IMPORT_BYTES = 5 * 1024 * 1024
MAX_IMPORT_ROWS = 500
MAX_XLSX_EXPANDED_BYTES = 25 * 1024 * 1024
MAX_XLSX_ENTRIES = 100
ALLOWED_COLUMNS = {
    "asset_id",
    "category",
    "parent_asset_id",
    "manufacturer",
    "model",
    "serial_number",
    "alias",
    "asset_subtype",
    "flash_code",
    "subscriber_id",
    "system_ids",
    "acquisition_date",
    "status",
    "notes",
}
REQUIRED_COLUMNS = {"asset_id", "category"}
TEXT_LIMITS = {
    "asset_id": 80,
    "parent_asset_id": 80,
    "manufacturer": 120,
    "model": 120,
    "serial_number": 160,
    "alias": 120,
    "asset_subtype": 80,
    "flash_code": 160,
    "subscriber_id": 80,
    "system_ids": 300,
    "notes": 5000,
}
CATEGORY_ALIASES = {
    "radio": Asset.Category.RADIO,
    "battery": Asset.Category.BATTERY,
    "antenna": Asset.Category.ANTENNA,
    "cable": Asset.Category.CABLE,
    "programming_cable": Asset.Category.CABLE,
    "microphone": Asset.Category.MICROPHONE,
    "accessory": Asset.Category.ACCESSORY,
    "other_accessory": Asset.Category.ACCESSORY,
}
STATUS_ALIASES = {
    "in_service": Asset.Status.IN_SERVICE,
    "spare": Asset.Status.SPARE,
    "maintenance": Asset.Status.MAINTENANCE,
    "retired": Asset.Status.RETIRED,
}


def _header(value):
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def _cell_text(cell, shared_strings, namespace):
    cell_type = cell.get("t")
    value = cell.find(f"{{{namespace}}}v")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.iter(f"{{{namespace}}}t"))
    if value is None or value.text is None:
        return ""
    if cell_type == "s":
        try:
            return shared_strings[int(value.text)]
        except (IndexError, ValueError):
            raise ValidationError("The XLSX shared-string table is invalid.") from None
    if cell_type == "b":
        return "true" if value.text == "1" else "false"
    return value.text


def _column_index(reference):
    letters = re.match(r"[A-Z]+", reference or "")
    if not letters:
        raise ValidationError("The XLSX contains an invalid cell reference.")
    result = 0
    for character in letters.group(0):
        result = result * 26 + ord(character) - ord("A") + 1
    return result - 1


def _xlsx_rows(content):
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        raise ValidationError("The XLSX file is not a valid workbook.") from None
    with archive:
        members = archive.infolist()
        if len(members) > MAX_XLSX_ENTRIES:
            raise ValidationError("The XLSX workbook contains too many internal files.")
        if sum(member.file_size for member in members) > MAX_XLSX_EXPANDED_BYTES:
            raise ValidationError("The expanded XLSX workbook exceeds 25 MiB.")
        names = {member.filename for member in members}
        if "xl/worksheets/sheet1.xml" not in names:
            raise ValidationError("The XLSX workbook must contain a first worksheet.")
        shared_strings = []
        if "xl/sharedStrings.xml" in names:
            shared_root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            namespace = shared_root.tag.split("}", 1)[0].lstrip("{")
            shared_strings = [
                "".join(node.text or "" for node in item.iter(f"{{{namespace}}}t"))
                for item in shared_root.findall(f"{{{namespace}}}si")
            ]
        root = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        namespace = root.tag.split("}", 1)[0].lstrip("{")
        rows = []
        for row in root.iter(f"{{{namespace}}}row"):
            values = {}
            for cell in row.findall(f"{{{namespace}}}c"):
                values[_column_index(cell.get("r"))] = _cell_text(cell, shared_strings, namespace)
            if values:
                rows.append([values.get(index, "") for index in range(max(values) + 1)])
        return rows


def _tabular_rows(filename, content):
    extension = Path(filename).suffix.lower()
    if extension == ".csv":
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise ValidationError("CSV files must use UTF-8 encoding.") from None
        if "\x00" in text:
            raise ValidationError("The CSV contains invalid null characters.")
        return list(csv.reader(io.StringIO(text)))
    if extension == ".xlsx":
        return _xlsx_rows(content)
    raise ValidationError("Upload a .csv or .xlsx file.")


def _normalize_rows(filename, content):
    if not content:
        raise ValidationError("The import file is empty.")
    if len(content) > MAX_IMPORT_BYTES:
        raise ValidationError("The import file exceeds 5 MiB.")
    table = _tabular_rows(filename, content)
    table = [row for row in table if any(str(value).strip() for value in row)]
    if not table:
        raise ValidationError("The import file has no rows.")
    headers = [_header(value) for value in table[0]]
    if len(headers) != len(set(headers)):
        raise ValidationError("The import file contains duplicate column headings.")
    missing = REQUIRED_COLUMNS - set(headers)
    if missing:
        raise ValidationError(f"Missing required columns: {', '.join(sorted(missing))}.")
    unsupported = set(headers) - ALLOWED_COLUMNS
    if unsupported:
        raise ValidationError(f"Unsupported columns: {', '.join(sorted(unsupported))}.")
    if len(table) - 1 > MAX_IMPORT_ROWS:
        raise ValidationError(f"Import files are limited to {MAX_IMPORT_ROWS} asset rows.")

    existing_ids = set(Asset.objects.values_list("asset_id", flat=True))
    seen_ids = set()
    rows = []
    errors = []
    for row_number, values in enumerate(table[1:], start=2):
        raw = {
            header: str(values[index] if index < len(values) else "").strip()
            for index, header in enumerate(headers)
            if header in ALLOWED_COLUMNS
        }
        row_errors = []
        asset_id = raw.get("asset_id", "")
        category_input = raw.get("category", "").lower().replace(" ", "_")
        category = CATEGORY_ALIASES.get(category_input, category_input)
        status_input = raw.get("status", "in_service").lower().replace(" ", "_") or "in_service"
        status = STATUS_ALIASES.get(status_input, status_input)
        if not asset_id:
            row_errors.append("asset_id is required")
        elif asset_id in seen_ids:
            row_errors.append("asset_id is duplicated in this file")
        elif asset_id in existing_ids:
            row_errors.append("asset_id already exists")
        if category not in Asset.Category.values:
            row_errors.append(f"category must be one of: {', '.join(Asset.Category.values)}")
        if status not in {
            Asset.Status.IN_SERVICE,
            Asset.Status.SPARE,
            Asset.Status.MAINTENANCE,
            Asset.Status.RETIRED,
        }:
            row_errors.append("status must be in_service, spare, maintenance, or retired")
        for field, limit in TEXT_LIMITS.items():
            if len(raw.get(field, "")) > limit:
                row_errors.append(f"{field} exceeds {limit} characters")
        acquisition_date = raw.get("acquisition_date", "")
        if acquisition_date:
            try:
                date.fromisoformat(acquisition_date)
            except ValueError:
                row_errors.append("acquisition_date must use YYYY-MM-DD")
        seen_ids.add(asset_id)
        normalized = {field: raw.get(field, "") for field in ALLOWED_COLUMNS}
        normalized.update(
            {
                "row_number": row_number,
                "category": category,
                "status": status,
                "acquisition_date": acquisition_date or None,
            }
        )
        rows.append(normalized)
        if row_errors:
            errors.append({"row_number": row_number, "asset_id": asset_id, "errors": row_errors})

    imported_ids = {row["asset_id"] for row in rows}
    imported_parents = {row["asset_id"]: row.get("parent_asset_id") for row in rows}
    for row in rows:
        parent_id = row.get("parent_asset_id")
        if parent_id and parent_id not in existing_ids and parent_id not in imported_ids:
            message = "parent_asset_id does not exist and is not included in this file"
            errors.append(
                {"row_number": row["row_number"], "asset_id": row["asset_id"], "errors": [message]}
            )
        visited = {row["asset_id"]}
        ancestor = parent_id
        while ancestor in imported_parents:
            if ancestor in visited:
                errors.append(
                    {
                        "row_number": row["row_number"],
                        "asset_id": row["asset_id"],
                        "errors": ["parent_asset_id creates a parent cycle"],
                    }
                )
                break
            visited.add(ancestor)
            ancestor = imported_parents[ancestor]
    return rows, errors


def preview_asset_import(*, uploaded_file, actor):
    content = uploaded_file.read(MAX_IMPORT_BYTES + 1)
    rows, errors = _normalize_rows(uploaded_file.name, content)
    batch = AssetImportBatch.objects.create(
        source_name=Path(uploaded_file.name).name[:255],
        source_sha256=hashlib.sha256(content).hexdigest(),
        rows=rows,
        errors=errors,
        row_count=len(rows),
        valid_count=len(rows) - len({error["row_number"] for error in errors}),
        created_by=actor,
    )
    record_event(
        actor=actor,
        action="inventory.asset_import_previewed",
        target=batch,
        details={
            "source_sha256": batch.source_sha256,
            "row_count": batch.row_count,
            "valid_count": batch.valid_count,
            "error_count": len(errors),
        },
    )
    return batch


@transaction.atomic
def commit_asset_import(*, batch, actor):
    batch = AssetImportBatch.objects.select_for_update().get(pk=batch.pk)
    if batch.status != AssetImportBatch.Status.PREVIEW:
        raise ValidationError("This import batch has already been committed.")
    if batch.errors:
        raise ValidationError("Correct every preview error before importing assets.")
    if Asset.objects.filter(asset_id__in=[row["asset_id"] for row in batch.rows]).exists():
        raise ValidationError("One or more asset IDs were created after preview. Preview again.")

    created = {}
    for row in batch.rows:
        values = {
            field: row.get(field, "")
            for field in ALLOWED_COLUMNS
            if field not in {"parent_asset_id", "acquisition_date"}
        }
        values["acquisition_date"] = row.get("acquisition_date")
        created[row["asset_id"]] = Asset.objects.create(created_by=actor, **values)
    existing_parents = {
        asset.asset_id: asset
        for asset in Asset.objects.filter(
            asset_id__in=[
                row.get("parent_asset_id") for row in batch.rows if row.get("parent_asset_id")
            ]
        )
    }
    for row in batch.rows:
        parent_id = row.get("parent_asset_id")
        if parent_id:
            asset = created[row["asset_id"]]
            asset.parent = created.get(parent_id) or existing_parents[parent_id]
            asset.save(update_fields=["parent", "updated_at"])

    batch.status = AssetImportBatch.Status.COMMITTED
    batch.committed_at = timezone.now()
    batch.save(update_fields=["status", "committed_at"])
    record_event(
        actor=actor,
        action="inventory.asset_import_committed",
        target=batch,
        details={"source_sha256": batch.source_sha256, "created_count": len(created)},
    )
    return list(created.values())
