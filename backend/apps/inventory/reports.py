from hashlib import sha256
from io import BytesIO
from pathlib import Path
from textwrap import wrap

from django.utils import timezone
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject
from reportlab.pdfgen import canvas

FORMS_DIRECTORY = Path(__file__).with_name("forms")
T_CARD_TEMPLATE = FORMS_DIRECTORY / "ics-form-219-7-v3.pdf"
ACCOUNTABLE_PROPERTY_TEMPLATE = FORMS_DIRECTORY / "ics-form-219-9-wf-2014.pdf"
T_CARD_SOURCE_URL = (
    "https://training.fema.gov/emiweb/is/icsresource/assets/ics%20forms/"
    "ics%20form%20219-7%2C%20t-card%20%28yellow%29%20%28v3%29.pdf"
)
ACCOUNTABLE_PROPERTY_SOURCE_URL = (
    "https://fs-prod-nwcg.s3.us-gov-west-1.amazonaws.com/icsproduct/ics_219_wf.pdf"
)
T_CARD_SHA256 = "4ccb3fd4063026271f5733cc4427143d7b4af7f65db3e6c997c82f774b855c53"
ACCOUNTABLE_PROPERTY_SHA256 = "3bc6fe853599f714989fdcaa51521bb490a4333aa97ad24764b657ceb18e9289"


def _local(value, pattern="%m/%d/%Y %H%M"):
    if not value:
        return ""
    if timezone.is_aware(value):
        value = timezone.localtime(value)
    return value.strftime(pattern)


def _clean(value, limit):
    return " ".join(str(value or "").split())[:limit]


def _wrapped(value, width, lines):
    words = " ".join(str(value or "").split())
    return "\n".join(wrap(words, width=width)[:lines])


def _resource_lines(checkout):
    asset = checkout.asset
    values = [
        asset.asset_id,
        f"Serial: {asset.serial_number}" if asset.serial_number else "",
        f"Alias: {asset.alias}" if asset.alias else "",
        f"Subscriber ID: {asset.subscriber_id}" if asset.subscriber_id else "",
        f"System IDs: {asset.system_ids}" if asset.system_ids else "",
        f"Model: {asset.manufacturer} {asset.model}".strip()
        if asset.manufacturer or asset.model
        else "",
    ]
    return [value for value in values if value][:8]


def render_equipment_t_card(checkout):
    asset = checkout.asset
    incident = checkout.incident
    category = asset.get_category_display()
    values = {
        "STUnit": _clean(checkout.assigned_organization, 5),
        " Pers": "1",
        "Order": _clean(incident.incident_number, 8),
        "Agency 1": _clean(checkout.assigned_organization, 8),
        "Cat 1": _clean(category, 7),
        "Kind 1": _clean(asset.asset_subtype or asset.model, 8),
        "Type 1": _clean(asset.manufacturer, 7),
        "Name/IS 1": _clean(asset.asset_id, 9),
        "DateTime Checked In_5": _local(checkout.checked_out_at),
        "Leader Name_5": _clean(checkout.assigned_name, 34),
        "Primary Contact Information_7": _clean(
            " / ".join(
                value for value in (checkout.point_of_contact, checkout.phone_number) if value
            ),
            100,
        ),
        "Home Base_11": _clean(checkout.assigned_organization, 45),
        "Remarks_12": _wrapped(checkout.assignment_notes, 38, 4),
        "Prepared by DateTime_19": _clean(
            f"{checkout.checked_out_by.get_username()} / {_local(timezone.now(), '%m/%d %H%M')}",
            20,
        ),
        "STUnit_2": _clean(checkout.assigned_organization, 5),
        " Pers_2": "1",
        "Order_2": _clean(incident.incident_number, 8),
        "Agency 2": _clean(checkout.assigned_organization, 8),
        "Cat 2": _clean(category, 7),
        "Kind 2": _clean(asset.asset_subtype or asset.model, 8),
        "Type 2": _clean(asset.manufacturer, 7),
        "Name/ID 2": _clean(asset.asset_id, 9),
        "Incident Location_26": _clean(incident.name, 20),
        "Time_29": _local(checkout.checked_out_at, "%H%M"),
        "Assigned 1": "/Yes" if checkout.state == checkout.State.ACTIVE else "/Off",
        "Available 1": "/Yes" if checkout.state == checkout.State.RETURNED else "/Off",
        "O/S Mech 1": (
            "/Yes"
            if checkout.state == checkout.State.HOLD
            and checkout.return_condition == checkout.ReturnCondition.DAMAGED
            else "/Off"
        ),
        "Notes_26": _wrapped(checkout.hold_reason or checkout.assignment_notes, 32, 4),
        "Prepared by DateTime_20": _clean(
            f"{checkout.checked_out_by.get_username()} / {_local(timezone.now(), '%m/%d %H%M')}",
            20,
        ),
    }
    for index, line in enumerate(_resource_lines(checkout), start=1):
        values[f"Resource ID s or NamesRow{index}_2"] = _clean(line, 60)

    reader = PdfReader(T_CARD_TEMPLATE)
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    writer.update_page_form_field_values(None, values, auto_regenerate=False, flatten=True)
    writer.remove_annotations(subtypes="/Widget")
    writer.root_object.pop(NameObject("/AcroForm"), None)
    writer.add_metadata(
        {
            "/Title": "ICS Form 219-7 - Equipment Resource Status Card",
            "/Author": "FEMA; populated by ICT Branch Toolkit",
            "/Subject": f"{incident.name} - {asset.asset_id}",
            "/Creator": "ICT Branch Toolkit",
            "/Producer": "pypdf",
        }
    )
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _draw_text(pdf, x, y, value, *, size=7, limit=52):
    pdf.setFont("Helvetica", size)
    pdf.drawString(x, y, _clean(value, limit))


def _overlay_accountable_property(checkout, maintenance_records):
    template = PdfReader(ACCOUNTABLE_PROPERTY_TEMPLATE)
    width = float(template.pages[0].mediabox.width)
    height = float(template.pages[0].mediabox.height)
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=(width, height), invariant=True)
    asset = checkout.asset

    for page_number in (1, 2):
        _draw_text(pdf, 67, 693, asset.asset_subtype or asset.get_category_display(), limit=16)
        _draw_text(pdf, 145, 693, checkout.assigned_organization, limit=20)
        _draw_text(pdf, 236, 693, asset.asset_id, limit=14)
        if page_number == 1:
            _draw_text(pdf, 83, 654, f"{asset.manufacturer} {asset.model}", limit=55)
            special = asset.notes or "Follow agency maintenance and charging procedures."
            _draw_text(pdf, 83, 545, special, limit=65)
            y = 385
            for record in maintenance_records[:4]:
                _draw_text(
                    pdf,
                    83,
                    y,
                    f"{_local(record.performed_at, '%m/%d/%Y')} - "
                    f"{record.get_kind_display()} - {record.technician}: {record.notes}",
                    limit=72,
                )
                y -= 29
            _draw_text(pdf, 83, 220, checkout.assignment_notes, limit=72)
            _draw_text(pdf, 150, 150, checkout.checked_out_by.get_username(), limit=28)
            _draw_text(pdf, 150, 133, _local(timezone.now()), limit=24)
        else:
            _draw_text(pdf, 83, 635, _local(checkout.checked_out_at), limit=25)
            _draw_text(pdf, 190, 635, "Not recorded", limit=38)
            _draw_text(pdf, 83, 603, checkout.assigned_name, limit=52)
            _draw_text(pdf, 83, 570, checkout.assigned_organization, limit=52)
            assignment = checkout.incident.name
            if checkout.incident.incident_number:
                assignment += f" ({checkout.incident.incident_number})"
            _draw_text(pdf, 83, 540, assignment, limit=63)
            if checkout.state == checkout.State.RETURNED:
                _draw_text(pdf, 88, 467, "X", size=9, limit=1)
                _draw_text(pdf, 110, 447, _local(checkout.returned_at, "%m/%d/%Y"), limit=20)
            elif checkout.state == checkout.State.HOLD:
                _draw_text(pdf, 83, 484, f"ACCOUNTABILITY HOLD: {checkout.hold_reason}", limit=62)
        pdf.showPage()
    pdf.save()
    return output.getvalue()


def render_accountable_property_record(checkout, maintenance_records):
    template = PdfReader(ACCOUNTABLE_PROPERTY_TEMPLATE)
    overlay = PdfReader(BytesIO(_overlay_accountable_property(checkout, maintenance_records)))
    writer = PdfWriter()
    writer.clone_document_from_reader(template)
    for page, overlay_page in zip(writer.pages, overlay.pages, strict=True):
        page.merge_page(overlay_page)
    writer.add_metadata(
        {
            "/Title": "ICS Form 219-9 WF - Accountable Property Assignment Record",
            "/Author": "NWCG; populated by ICT Branch Toolkit",
            "/Subject": f"{checkout.incident.name} - {checkout.asset.asset_id}",
            "/Creator": "ICT Branch Toolkit",
            "/Producer": "pypdf and ReportLab",
        }
    )
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def report_digest(content):
    return sha256(content).hexdigest()
