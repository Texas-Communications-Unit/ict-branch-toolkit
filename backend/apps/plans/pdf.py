from io import BytesIO
from pathlib import Path

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject

FORM_TEMPLATE = Path(__file__).with_name("forms") / "ics-form-205-v3.1.pdf"
FORM_SOURCE_URL = (
    "https://training.fema.gov/emiweb/is/icsresource/assets/ics%20forms/"
    "ics%20form%20205,%20incident%20radio%20communications%20plan%20(v3.1).pdf"
)
FORM_SHA256 = "cbe54dc5ae6de7af1d01f5c84c68031645f5d92b095763b3667ed13efd872377"
ROWS_PER_PAGE = 8


def _local_date_and_time(value):
    if value is None:
        return "", ""
    if isinstance(value, str):
        value = parse_datetime(value)
        if value is None:
            return "", ""
    if timezone.is_aware(value):
        value = timezone.localtime(value)
    return value.strftime("%m/%d/%Y"), value.strftime("%H%M")


def _bandwidth_designator(item):
    snapshot = item.resource_snapshot if isinstance(item.resource_snapshot, dict) else {}
    bandwidth = snapshot.get("bandwidth_hz") or snapshot.get("emission_bandwidth_hz")
    try:
        bandwidth = int(bandwidth)
    except (TypeError, ValueError):
        return ""
    return "N" if bandwidth <= 12_500 else "W"


def _frequency(item, value):
    if value is None:
        return ""
    designation = _bandwidth_designator(item)
    return f"{value / 1_000_000:.4f}{f' {designation}' if designation else ''}"


def _official_mode(value):
    normalized = value.strip().upper()
    if normalized in {"A", "D", "M"}:
        return normalized
    if "MIX" in normalized:
        return "M"
    if "ANALOG" in normalized or normalized in {"FM", "FMN"}:
        return "A"
    if any(marker in normalized for marker in ("DIGITAL", "P25", "DMR", "NXDN")):
        return "D"
    return ""


def _published_contact_lines(revision):
    lines = []
    labels = {
        "contact_name": "Contact",
        "site_address": "Site address",
        "phone_numbers": "Phone",
        "contact_24_hour": "24-hour contact",
    }
    for item in revision.assignments.all():
        if (
            item.contact_publication_placement
            != item.ContactPublicationPlacement.SPECIAL_INSTRUCTIONS
        ):
            continue
        contacts = [
            f"{labels[field]}: {getattr(item, field)}"
            for field in item.published_contact_fields
            if field in labels and getattr(item, field)
        ]
        if contacts:
            contacts.append(f"Publication purpose: {item.contact_publication_purpose}")
            lines.append(f"Row {item.position} ({item.channel_name}) - " + " - ".join(contacts))
    return lines


def _remarks(item):
    note = item.get_structured_note_display() if item.structured_note else ""
    operating_note = ""
    if item.operating_classification != item.OperatingClassification.FIXED_PAIR:
        operating_note = item.get_operating_classification_display()
        if item.technology_subtype:
            operating_note = f"{operating_note}: {item.get_technology_subtype_display()}"

    contacts = []
    if item.contact_publication_placement == item.ContactPublicationPlacement.REMARKS:
        labels = {
            "contact_name": "Contact",
            "site_address": "Site address",
            "phone_numbers": "Phone",
            "contact_24_hour": "24-hour contact",
        }
        contacts = [
            f"{labels[field]}: {getattr(item, field)}"
            for field in item.published_contact_fields
            if field in labels and getattr(item, field)
        ]
        if contacts:
            contacts.append(f"Publication purpose: {item.contact_publication_purpose}")

    mode_note = item.mode if item.mode and not _official_mode(item.mode) else ""
    return " - ".join(
        part for part in (operating_note, note, item.remarks, mode_note, *contacts) if part
    )


def _page_values(revision, assignments, *, page_number, page_count, approval_preview):
    prepared_at = revision.prepared_at or revision.approved_at or revision.updated_at
    prepared_date, prepared_time = _local_date_and_time(prepared_at)
    period_start_date, period_start_time = _local_date_and_time(
        revision.plan.operational_period.starts_at
    )
    period_end_date, period_end_time = _local_date_and_time(
        revision.plan.operational_period.ends_at
    )
    values = {
        "1 Incident Name_8": revision.plan.incident.name,
        "2 Date/Time Prepared": prepared_date,
        "Date From": period_start_date,
        "Date To": period_end_date,
        "Time From": period_start_time,
        "Time To": period_end_time,
        "6 Prepared by Communications Unit Leader Name": revision.prepared_by_name,
        "IAP Page_4": "",
        "DateTime_8": f"{prepared_date} {prepared_time}".strip(),
    }

    special_instructions = []
    if approval_preview:
        special_instructions.append("DRAFT APPROVAL PREVIEW - NOT APPROVED")
    if page_count > 1:
        special_instructions.append(f"ICS 205 continuation {page_number} of {page_count}")
    if page_number == 1:
        special_instructions.extend(_published_contact_lines(revision))
        special_instructions.append(
            "Planning output only. This form is not frequency coordination approval, spectrum "
            "authorization, a propagation study, or a guarantee of coverage."
        )
    values["5 Special Instructions"] = "\n".join(special_instructions)

    for row_number in range(1, ROWS_PER_PAGE + 1):
        item = assignments[row_number - 1] if row_number <= len(assignments) else None
        values.update(
            {
                f"Zone GrpRow{row_number}": "",
                f"Ch Row{row_number}": str(item.position) if item else "",
                f"FunctionRow{row_number}": item.function if item else "",
                f"Channel NameTrunked Radio System TalkgroupRow{row_number}": (
                    item.channel_name if item else ""
                ),
                f"AssignmentRow{row_number}": item.assignment if item else "",
                f"RX Freq N or WRow{row_number}": (
                    _frequency(item, item.rx_frequency_hz) if item else ""
                ),
                f"RX ToneNACRow{row_number}": item.rx_squelch if item else "",
                f"TX Freq N or WRow{row_number}": (
                    _frequency(item, item.tx_frequency_hz) if item else ""
                ),
                f"TX ToneNACRow{row_number}": item.tx_squelch if item else "",
                f"Mode A D or MRow{row_number}": _official_mode(item.mode) if item else "",
                f"RemarksRow{row_number}": _remarks(item) if item else "",
            }
        )
    return values


def _render_official_page(values):
    reader = PdfReader(FORM_TEMPLATE)
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    del writer.pages[2]
    del writer.pages[1]
    writer.update_page_form_field_values(
        writer.pages[0],
        values,
        auto_regenerate=False,
        flatten=True,
    )
    writer.remove_annotations(subtypes="/Widget")
    writer.root_object.pop(NameObject("/AcroForm"), None)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def render_ics205(revision, *, approval_preview=False):
    if not revision.is_locked and not approval_preview:
        raise ValueError("Official PDF export requires an approved revision.")

    assignments = list(revision.assignments.all())
    page_count = max(1, (len(assignments) + ROWS_PER_PAGE - 1) // ROWS_PER_PAGE)
    output = PdfWriter()
    for page_index in range(page_count):
        page_assignments = assignments[
            page_index * ROWS_PER_PAGE : (page_index + 1) * ROWS_PER_PAGE
        ]
        values = _page_values(
            revision,
            page_assignments,
            page_number=page_index + 1,
            page_count=page_count,
            approval_preview=approval_preview,
        )
        rendered = PdfReader(BytesIO(_render_official_page(values)))
        output.add_page(rendered.pages[0])

    output.add_metadata(
        {
            "/Title": "ICS Form 205 - Incident Radio Communications Plan",
            "/Author": "FEMA; populated by ICT Branch Toolkit",
            "/Subject": f"Official FEMA ICS Form 205 v3.1; revision {revision.number}",
            "/Creator": "ICT Branch Toolkit",
            "/Producer": "pypdf",
        }
    )
    destination = BytesIO()
    output.write(destination)
    return destination.getvalue()
