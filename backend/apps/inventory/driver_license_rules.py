import re

from rest_framework.exceptions import ValidationError

RULESET_VERSION = "us-state-license-input-v1-2026-08-22"

# Conservative input-quality bounds keyed by issuing jurisdiction. These rules intentionally do
# not attempt identity verification and allow legacy formats within each issuer's upper bound.
MAX_LENGTH_BY_JURISDICTION = {
    "AL": 8,
    "AK": 7,
    "AZ": 9,
    "AR": 9,
    "CA": 8,
    "CO": 9,
    "CT": 9,
    "DE": 7,
    "DC": 7,
    "FL": 13,
    "GA": 9,
    "HI": 9,
    "ID": 9,
    "IL": 12,
    "IN": 10,
    "IA": 9,
    "KS": 9,
    "KY": 9,
    "LA": 9,
    "ME": 8,
    "MD": 13,
    "MA": 9,
    "MI": 13,
    "MN": 13,
    "MS": 9,
    "MO": 10,
    "MT": 13,
    "NE": 9,
    "NV": 12,
    "NH": 10,
    "NJ": 15,
    "NM": 9,
    "NY": 16,
    "NC": 12,
    "ND": 9,
    "OH": 8,
    "OK": 10,
    "OR": 9,
    "PA": 8,
    "RI": 7,
    "SC": 11,
    "SD": 8,
    "TN": 9,
    "TX": 8,
    "UT": 10,
    "VT": 8,
    "VA": 9,
    "WA": 12,
    "WV": 7,
    "WI": 14,
    "WY": 10,
}


def normalize_and_validate(jurisdiction: str, number: str) -> tuple[str, str]:
    issuer = jurisdiction.strip().upper()
    maximum = MAX_LENGTH_BY_JURISDICTION.get(issuer)
    if maximum is None:
        raise ValidationError(
            {"driver_license_jurisdiction": "Select a U.S. state or the District of Columbia."}
        )
    normalized = re.sub(r"[ -]", "", number.strip().upper())
    if not re.fullmatch(r"[A-Z0-9]+", normalized or ""):
        raise ValidationError(
            {"driver_license_number": "Use only letters, numbers, spaces, or hyphens."}
        )
    if not 4 <= len(normalized) <= maximum:
        raise ValidationError(
            {
                "driver_license_number": (
                    f"{issuer} license numbers must contain 4 to {maximum} letters or numbers "
                    f"under input rule {RULESET_VERSION}."
                )
            }
        )
    return issuer, normalized
