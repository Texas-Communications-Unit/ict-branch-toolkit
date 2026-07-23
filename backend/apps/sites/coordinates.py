import re
from dataclasses import dataclass

import mgrs
from mgrs.core import MGRSError


class CoordinateError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedCoordinate:
    latitude: float
    longitude: float
    input_format: str


def _component(text: str, axis: str) -> tuple[float, str]:
    cleaned = text.strip().upper().replace("º", "°")
    hemispheres = re.findall(r"[NSEW]", cleaned)
    if len(hemispheres) > 1:
        raise CoordinateError("Use one hemisphere letter per coordinate.")
    hemisphere = hemispheres[0] if hemispheres else ""
    if hemisphere and (
        (axis == "latitude" and hemisphere not in "NS")
        or (axis == "longitude" and hemisphere not in "EW")
    ):
        raise CoordinateError(f"{hemisphere} is not valid for {axis}.")
    numbers = [float(value) for value in re.findall(r"[-+]?\d+(?:\.\d+)?", cleaned)]
    if not 1 <= len(numbers) <= 3:
        raise CoordinateError("Use decimal degrees, DDM, or DMS for each coordinate.")
    degrees = numbers[0]
    minutes = numbers[1] if len(numbers) >= 2 else 0.0
    seconds = numbers[2] if len(numbers) == 3 else 0.0
    if minutes >= 60 or seconds >= 60:
        raise CoordinateError("Minutes and seconds must be less than 60.")
    if len(numbers) > 1 and degrees < 0:
        raise CoordinateError("Use a hemisphere letter with unsigned DDM or DMS degrees.")
    magnitude = abs(degrees) + minutes / 60 + seconds / 3600
    sign = -1 if degrees < 0 or (hemisphere and hemisphere in "SW") else 1
    value = sign * magnitude
    limit = 90 if axis == "latitude" else 180
    if not -limit <= value <= limit:
        raise CoordinateError(f"{axis.title()} must be between {-limit} and {limit}.")
    return value, ("decimal" if len(numbers) == 1 else "ddm" if len(numbers) == 2 else "dms")


def parse_coordinate(text: str) -> ParsedCoordinate:
    original = text.strip()
    if not original:
        raise CoordinateError("Enter a coordinate.")
    compact = re.sub(r"\s+", "", original).upper()
    if re.fullmatch(r"\d{1,2}[C-HJ-NP-X][A-HJ-NP-Z]{2}\d{2,10}", compact):
        try:
            latitude, longitude = mgrs.MGRS().toLatLon(compact)
        except (MGRSError, ValueError) as exc:
            raise CoordinateError("The USNG/MGRS coordinate is invalid or incomplete.") from exc
        return ParsedCoordinate(latitude, longitude, "mgrs")

    parts = re.split(r"\s*[,;]\s*", original)
    if len(parts) == 1:
        decimal_pair = re.fullmatch(r"\s*([-+]?\d+(?:\.\d+)?)\s+([-+]?\d+(?:\.\d+)?)\s*", original)
        if decimal_pair:
            parts = [decimal_pair.group(1), decimal_pair.group(2)]
    if len(parts) != 2:
        raise CoordinateError("Separate latitude and longitude with a comma.")
    latitude, latitude_format = _component(parts[0], "latitude")
    longitude, longitude_format = _component(parts[1], "longitude")
    input_format = latitude_format if latitude_format == longitude_format else "dms"
    return ParsedCoordinate(latitude, longitude, input_format)


def _dms(value: float, positive: str, negative: str) -> str:
    hemisphere = positive if value >= 0 else negative
    absolute = abs(value)
    degrees = int(absolute)
    minutes_full = (absolute - degrees) * 60
    minutes = int(minutes_full)
    seconds = (minutes_full - minutes) * 60
    return f"{degrees}° {minutes:02d}′ {seconds:05.2f}″ {hemisphere}"


def _ddm(value: float, positive: str, negative: str) -> str:
    hemisphere = positive if value >= 0 else negative
    absolute = abs(value)
    degrees = int(absolute)
    minutes = (absolute - degrees) * 60
    return f"{degrees}° {minutes:07.4f}′ {hemisphere}"


def coordinate_formats(latitude: float, longitude: float) -> dict[str, str]:
    return {
        "decimal": f"{latitude:.6f}, {longitude:.6f}",
        "ddm": f"{_ddm(latitude, 'N', 'S')}, {_ddm(longitude, 'E', 'W')}",
        "dms": f"{_dms(latitude, 'N', 'S')}, {_dms(longitude, 'E', 'W')}",
        "mgrs": mgrs.MGRS().toMGRS(latitude, longitude, MGRSPrecision=5),
    }
