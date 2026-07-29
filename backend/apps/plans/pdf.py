from io import BytesIO
from xml.sax.saxutils import escape

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    TableStyle,
)


def _mhz(value):
    return "" if value is None else f"{value / 1_000_000:.6f}"


def render_ics205(revision, *, approval_preview=False):
    if not revision.is_locked and not approval_preview:
        raise ValueError("Official PDF export requires an approved revision.")
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=landscape(letter),
        leftMargin=0.35 * inch,
        rightMargin=0.35 * inch,
        topMargin=0.35 * inch,
        bottomMargin=0.4 * inch,
        title="ICS 205 Incident Radio Communications Plan",
        author="ICT Branch Toolkit",
        invariant=True,
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph("<b>INCIDENT RADIO COMMUNICATIONS PLAN (ICS 205)</b>", styles["Title"]),
        Spacer(1, 8),
        LongTable(
            [
                [
                    "1. Incident Name",
                    revision.plan.incident.name,
                    "2. Operational Period",
                    revision.plan.operational_period.name,
                ],
                [
                    "Incident Number",
                    revision.plan.incident.incident_number or "",
                    "Revision",
                    str(revision.number),
                ],
            ],
            colWidths=[1.25 * inch, 3.25 * inch, 1.35 * inch, 4.2 * inch],
            style=TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.75, colors.black),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e8edf2")),
                    ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#e8edf2")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ]
            ),
        ),
        Spacer(1, 10),
    ]
    headers = [
        "Ch #",
        "Function",
        "Channel / Talkgroup",
        "Assignment",
        "RX MHz",
        "RX Tone/NAC",
        "TX MHz",
        "TX Tone/NAC",
        "Mode",
        "Remarks",
    ]
    rows = [headers]
    special_instruction_lines = []
    for item in revision.assignments.all():
        note = item.get_structured_note_display() if item.structured_note else ""
        operating_note = ""
        if item.operating_classification != item.OperatingClassification.FIXED_PAIR:
            operating_note = item.get_operating_classification_display()
            if item.technology_subtype:
                operating_note = f"{operating_note}: {item.get_technology_subtype_display()}"
        published_contact_labels = {
            "contact_name": "Contact",
            "site_address": "Site address",
            "phone_numbers": "Phone",
            "contact_24_hour": "24-hour contact",
        }
        published_contacts = [
            f"{published_contact_labels[field]}: {getattr(item, field)}"
            for field in item.published_contact_fields
            if field in published_contact_labels and getattr(item, field)
        ]
        if published_contacts:
            published_contacts.append(f"Publication purpose: {item.contact_publication_purpose}")
        row_contacts = published_contacts
        if (
            item.contact_publication_placement
            == item.ContactPublicationPlacement.SPECIAL_INSTRUCTIONS
        ):
            row_contacts = []
            special_instruction_lines.append(
                f"Row {item.position} ({item.channel_name}) — " + " - ".join(published_contacts)
            )
        remarks = " - ".join(
            part
            for part in [
                operating_note,
                note,
                item.remarks,
                *row_contacts,
            ]
            if part
        )
        rows.append(
            [
                str(item.position),
                item.function,
                item.channel_name,
                item.assignment,
                _mhz(item.rx_frequency_hz),
                item.rx_squelch,
                _mhz(item.tx_frequency_hz),
                item.tx_squelch,
                item.mode,
                remarks,
            ]
        )
    table = LongTable(
        rows,
        repeatRows=1,
        colWidths=[
            0.38 * inch,
            0.9 * inch,
            1.25 * inch,
            1.1 * inch,
            0.75 * inch,
            0.7 * inch,
            0.75 * inch,
            0.7 * inch,
            0.65 * inch,
            2.4 * inch,
        ],
        style=TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbe5ef")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 6.8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ]
        ),
    )
    story.append(table)
    if special_instruction_lines:
        story.extend(
            [
                Spacer(1, 8),
                Paragraph(
                    "<b>Special Instructions</b><br/>"
                    + "<br/>".join(escape(line) for line in special_instruction_lines),
                    styles["Normal"],
                ),
            ]
        )
    story.extend(
        [
            Spacer(1, 10),
            Paragraph(
                f"<b>Prepared by:</b> {escape(revision.prepared_by_name)} &nbsp;&nbsp; "
                f"<b>Position:</b> {escape(revision.prepared_by_position)} &nbsp;&nbsp; "
                f"<b>{'Approval preview' if approval_preview else 'Approved revision'}:</b> "
                f"{revision.number}",
                styles["Normal"],
            ),
            Spacer(1, 3),
            Paragraph(
                f"<b>Status:</b> {'DRAFT APPROVAL PREVIEW' if approval_preview else 'APPROVED'} "
                f"&nbsp;&nbsp; <b>Approved at:</b> "
                f"{escape(revision.approved_at.isoformat() if revision.approved_at else '')} "
                f"&nbsp;&nbsp; <b>App version:</b> {escape(settings.APP_VERSION)}",
                styles["Normal"],
            ),
            Spacer(1, 5),
            Paragraph(
                "Planning output. This document is not frequency coordination approval, "
                "spectrum authorization, a propagation study, or a guarantee of coverage.",
                styles["Normal"],
            ),
        ]
    )

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.drawString(
            0.35 * inch,
            0.18 * inch,
            f"ICS 205 - {revision.plan.incident.incident_number or revision.plan.incident.name} "
            f"- Revision {revision.number}",
        )
        canvas.drawRightString(10.65 * inch, 0.18 * inch, f"Page {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
