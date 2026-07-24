#!/usr/bin/env python3
"""Build the reviewed NIFOG 2.02 channel-library payload from the official PDF."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path

import pdfplumber

SOURCE_URL = (
    "https://www.cisa.gov/sites/default/files/2024-12/"
    "NIFOG%202.02_508%20FINAL%20VERSION%2012%2003%202024.pdf"
)
EXPECTED_SHA256 = "45c2f5d94861b3ed1b80f7ce5962a160fdd56092211586bdee711b68ca3d3142"
GLOBAL_AUTHORIZATION = (
    "The NIFOG is reference material and does not itself authorize operation. "
    "Use requires applicable FCC or NTIA authority and compliance with the "
    "conditions in NIFOG 2.02."
)

STANDARD_CHANNEL_PAGES = [
    35,
    36,
    37,
    38,
    41,
    42,
    43,
    45,
    46,
    47,
    48,
    49,
    50,
    51,
    52,
    53,
    54,
    55,
    56,
    57,
    58,
    59,
    60,
    61,
    66,
]
TALKGROUP_PAGES = [62, 63, 64, 65]


def normalized(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\n", " ").split())


def pdf_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def mhz_to_hz(value: str) -> int:
    return int(Decimal(value) * Decimal(1_000_000))


def is_frequency(value: str) -> bool:
    return bool(re.fullmatch(r"\d+\.\d+", value))


def printed_page(pdf_page: int) -> str:
    return str(pdf_page - 7)


def band_for_frequency(frequency_mhz: str) -> str:
    frequency = Decimal(frequency_mhz)
    if frequency < 50:
        return "VHF Low Band"
    if frequency < 300:
        return "VHF"
    if frequency < 500:
        return "UHF"
    if frequency < 800:
        return "700 MHz"
    return "800 MHz"


def mode_for_page(pdf_page: int, name: str, assignment: str) -> str:
    if 52 <= pdf_page <= 59 or pdf_page == 61:
        return "p25"
    if pdf_page == 60:
        return "other"
    if pdf_page in (43, 47):
        analog_names = {"LE A", "LE 1", "LE B", "LE 10"}
        return "analog_fm" if name in analog_names or "Analog" in assignment else "p25"
    if pdf_page == 44:
        return "other"
    return "analog_fm"


def section_for_table(table: list[list[object]]) -> str:
    title = normalized(table[0][0])
    if len(table) < 2:
        return title
    subtitle = normalized(table[1][0])
    if (
        subtitle
        and len(subtitle) <= 90
        and not subtitle.startswith(("LICENSING REQUIRED", "TX NAC:", "Assignment"))
    ):
        return f"{title} - {subtitle}"
    return title


def row_columns(pdf_page: int, row: list[object]) -> list[str]:
    padded = [*row, *([None] * 8)]
    if pdf_page == 52:
        selected = [padded[index] for index in (0, 1, 3, 4, 6, 7)]
    elif pdf_page == 61:
        selected = [padded[index] for index in (0, 1, 2, 4, 5, 6)]
    else:
        selected = padded[:6]
    return [normalized(value) for value in selected]


def page_restrictions(pdf_page: int, table: list[list[object]]) -> str:
    fragments: list[str] = []
    section = section_for_table(table)
    subtitle = normalized(table[1][0]) if len(table) > 1 else ""
    subtitle_is_section = section.endswith(f" - {subtitle}") if subtitle else False
    for index, row in enumerate(table):
        columns = row_columns(pdf_page, row)
        if len(columns) >= 3 and columns[1] and is_frequency(columns[2]):
            continue
        text = normalized(" ".join(value for value in columns if value))
        if not text:
            continue
        if index == 0 or (index == 1 and subtitle_is_section):
            continue
        if "Mobile RX" in text or text.startswith("Assignment Channel Name"):
            continue
        if text.isdigit():
            continue
        if len(text) >= 20:
            fragments.append(text)
    return "\n".join(dict.fromkeys(fragments))


def emission_from(restrictions: str, mode: str) -> str:
    match = re.search(r"\b\d{1,2}K[0-9A-Z]+\b", restrictions)
    if match:
        return match.group(0)
    if mode == "p25":
        return "8K10F1E"
    return ""


def bandwidth_from_emission(emission_designator: str) -> int | None:
    match = re.match(r"(?P<whole>\d{1,2})K(?P<fraction>\d{1,2})", emission_designator)
    if not match:
        return None
    fraction = match.group("fraction").ljust(3, "0")
    return int(match.group("whole")) * 1_000 + int(fraction)


def clean_squelch(value: str) -> str:
    if value in {"“ ”", '" "'}:
        return "See Notes"
    if re.fullmatch(r"-+", value):
        return ""
    return value.replace("\n", " / ")


def add_source_page(record: dict[str, object], page: str, restrictions: str) -> None:
    pages = [
        item.strip() for item in str(record["source_pages"]).split(",") if item.strip()
    ]
    if page not in pages:
        pages.append(page)
    record["source_pages"] = ", ".join(pages)
    if restrictions and restrictions not in str(record["restrictions"]):
        record["restrictions"] = f"{record['restrictions']}\n{restrictions}".strip()


def conventional_record(
    *,
    pdf_page: int,
    section: str,
    assignment: str,
    name: str,
    rx_mhz: str,
    rx_squelch: str,
    tx_mhz: str,
    tx_squelch: str,
    restrictions: str,
) -> dict[str, object]:
    mode = mode_for_page(pdf_page, name, assignment)
    emission_designator = emission_from(restrictions, mode)
    jurisdiction = (
        "Federal interoperability" if pdf_page in {42, 43, 46, 47} else "Nationwide"
    )
    if pdf_page in {41, 44, 48, 49, 50, 51}:
        jurisdiction = "United States"
    return {
        "identifier": (
            f"DEPLOY-{name.rstrip('*•').strip()}"
            if pdf_page == 61
            else name.rstrip("*•").strip()
        ),
        "name": name.rstrip("*•").strip(),
        "channel_use": assignment,
        "band": band_for_frequency(rx_mhz),
        "jurisdiction": jurisdiction,
        "rx_frequency_hz": mhz_to_hz(rx_mhz),
        "tx_frequency_hz": mhz_to_hz(tx_mhz) if tx_mhz else None,
        "bandwidth_hz": bandwidth_from_emission(emission_designator),
        "mode": mode,
        "rx_squelch": clean_squelch(rx_squelch),
        "tx_squelch": clean_squelch(tx_squelch),
        "emission_designator": emission_designator,
        "eligibility": assignment,
        "authorization": GLOBAL_AUTHORIZATION,
        "source_section": section,
        "source_pages": printed_page(pdf_page),
        "restrictions": restrictions,
        "notes": "",
        "is_active": True,
    }


def extract_standard_channels(pdf: pdfplumber.PDF) -> dict[str, dict[str, object]]:
    channels: dict[str, dict[str, object]] = {}
    for pdf_page in STANDARD_CHANNEL_PAGES:
        table = pdf.pages[pdf_page - 1].extract_tables()[0]
        section = section_for_table(table)
        restrictions = page_restrictions(pdf_page, table)
        for row in table:
            columns = row_columns(pdf_page, row)
            assignment, name, rx_mhz, rx_squelch, tx_mhz, tx_squelch = columns
            if not name or not is_frequency(rx_mhz):
                continue
            if pdf_page == 60 and not rx_squelch:
                rx_squelch = "156.7 / $F7E"
                tx_squelch = "156.7 / $293"
            record = conventional_record(
                pdf_page=pdf_page,
                section=section,
                assignment=assignment,
                name=name,
                rx_mhz=rx_mhz,
                rx_squelch=rx_squelch,
                tx_mhz=tx_mhz,
                tx_squelch=tx_squelch,
                restrictions=restrictions,
            )
            identifier = str(record["identifier"])
            if identifier in channels:
                raise ValueError(f"Duplicate NIFOG channel identifier: {identifier}")
            channels[identifier] = record
    return channels


def add_weather_channels(
    pdf: pdfplumber.PDF, channels: dict[str, dict[str, object]]
) -> None:
    pdf_page = 44
    table = pdf.pages[pdf_page - 1].extract_tables()[0]
    section = normalized(table[0][0])
    for cell in table[1]:
        frequency = normalized(cell)
        if not is_frequency(frequency):
            continue
        identifier = f"WX-{frequency.replace('.', '')}"
        channels[identifier] = conventional_record(
            pdf_page=pdf_page,
            section=section,
            assignment="Weather broadcast receive only",
            name=identifier,
            rx_mhz=frequency,
            rx_squelch="",
            tx_mhz="",
            tx_squelch="",
            restrictions="Receive only.",
        )


def add_sar_plan(pdf: pdfplumber.PDF, channels: dict[str, dict[str, object]]) -> None:
    pdf_page = 70
    table = pdf.pages[pdf_page - 1].extract_tables()[0]
    section = normalized(table[0][0])
    restrictions = normalized(table[-1][0])
    for row in table[2:-1]:
        columns = [normalized(value) for value in [*row, *([None] * 6)][:6]]
        _, name, rx_mhz, rx_squelch, tx_mhz, tx_squelch = columns
        if not name or not is_frequency(rx_mhz):
            continue
        clean_name = name.rstrip("*").strip()
        if clean_name in channels:
            add_source_page(channels[clean_name], printed_page(pdf_page), restrictions)
            continue
        channels[clean_name] = conventional_record(
            pdf_page=pdf_page,
            section=section,
            assignment="SAR command interoperability",
            name=clean_name,
            rx_mhz=rx_mhz,
            rx_squelch=rx_squelch,
            tx_mhz=tx_mhz,
            tx_squelch=tx_squelch,
            restrictions=restrictions,
        )


def extract_talkgroups(pdf: pdfplumber.PDF) -> list[dict[str, object]]:
    talkgroups: list[dict[str, object]] = []
    for pdf_page in TALKGROUP_PAGES:
        table = pdf.pages[pdf_page - 1].extract_tables()[0]
        section = f"{normalized(table[0][0])} - {normalized(table[1][0])}"
        zone_match = re.search(r"Zone [“\"]([A-Z]{2}) DEPLOY", section)
        if not zone_match:
            raise ValueError(
                f"Unable to determine deployable zone on PDF page {pdf_page}"
            )
        zone = zone_match.group(1)
        for row in table:
            padded = [normalized(value) for value in [*row, *([None] * 5)][:5]]
            _, name, eligibility, decimal_id, hex_id = padded
            if not name or not decimal_id.isdigit():
                continue
            talkgroups.append(
                {
                    "identifier": f"{zone}-{name.replace(' ', '-')}",
                    "name": name,
                    "system_name": f"NIFOG 700 MHz {zone} DEPLOY - System ID $101",
                    "talkgroup_id": int(decimal_id),
                    "mode": "P25 Phase I",
                    "eligibility": eligibility,
                    "authorization": GLOBAL_AUTHORIZATION,
                    "source_section": section,
                    "source_pages": printed_page(pdf_page),
                    "restrictions": (
                        "Coordinate the unique NAC with the National Regional Planning "
                        f"Council. Source TG hexadecimal ID: {hex_id}."
                    ),
                    "notes": "",
                    "is_active": True,
                }
            )
    return talkgroups


def build_payload(pdf_path: Path) -> dict[str, object]:
    actual_sha256 = pdf_sha256(pdf_path)
    if actual_sha256 != EXPECTED_SHA256:
        raise ValueError(
            f"NIFOG PDF SHA-256 mismatch: expected {EXPECTED_SHA256}, got {actual_sha256}"
        )
    with pdfplumber.open(pdf_path) as pdf:
        if len(pdf.pages) != 192:
            raise ValueError(f"Expected 192 PDF pages, found {len(pdf.pages)}")
        channels = extract_standard_channels(pdf)
        add_weather_channels(pdf, channels)
        add_sar_plan(pdf, channels)
        talkgroups = extract_talkgroups(pdf)

    conventional = sorted(channels.values(), key=lambda item: str(item["identifier"]))
    talkgroups.sort(key=lambda item: str(item["identifier"]))
    if len(conventional) != 230 or len(talkgroups) != 32:
        raise ValueError(
            "Unexpected NIFOG record counts: "
            f"{len(conventional)} conventional, {len(talkgroups)} talkgroups"
        )
    return {
        "dry_run": True,
        "source": {
            "slug": "cisa-nifog",
            "name": "National Interoperability Field Operations Guide",
            "source_type": "cisa_nifog",
            "authoritative_url": SOURCE_URL,
        },
        "release": {
            "version": "2.02",
            "released_on": None,
            "effective_status": "effective",
            "content_sha256": EXPECTED_SHA256,
            "document_title": "National Interoperability Field Operations Guide Version 2.02",
            "publisher": "Cybersecurity and Infrastructure Security Agency",
            "retrieved_on": "2026-07-23",
            "permitted_use": (
                "Public field reference material. Structured records remain subject to "
                "the authorization, eligibility, coordination, and usage conditions in "
                "the source document."
            ),
            "transformation_method": (
                "Deterministic extraction of the interoperability channel tables on "
                "printed pages 28-59 and the SAR command plan on printed page 63, "
                "followed by record-count, schema, checksum, and visual sample review."
            ),
        },
        "conventional_channels": conventional,
        "trunked_talkgroups": talkgroups,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path, help="Path to the official NIFOG 2.02 PDF")
    parser.add_argument("--output", type=Path, help="Write JSON to this path")
    args = parser.parse_args()
    payload = build_payload(args.pdf)
    rendered = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
