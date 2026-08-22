from __future__ import annotations

import hashlib
import io
import zipfile
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath

from django.core.exceptions import ValidationError

from .models import FccImportBatch

PARSER_VERSION = "fcc-public-access-v1"
MAX_ARCHIVE_BYTES = 1_000_000_000
MAX_EXPANDED_BYTES = 5_000_000_000
MAX_MEMBER_BYTES = 1_000_000_000
MAX_MEMBERS = 64
MAX_LINE_BYTES = 65_536
MAX_RECORDS = 20_000_000

EXPECTED_ARCHIVES = {
    FccImportBatch.Dataset.ASR: "r_tower.zip",
    FccImportBatch.Dataset.ULS_PRIVATE: "l_LMpriv.zip",
    FccImportBatch.Dataset.ULS_COMMERCIAL: "l_LMcomm.zip",
}
REQUIRED_MEMBERS = {
    FccImportBatch.Dataset.ASR: {"RA.dat", "CO.dat", "EN.dat"},
    FccImportBatch.Dataset.ULS_PRIVATE: {"HD.dat", "EN.dat", "LO.dat", "FR.dat", "EM.dat"},
    FccImportBatch.Dataset.ULS_COMMERCIAL: {
        "HD.dat",
        "EN.dat",
        "LO.dat",
        "FR.dat",
        "EM.dat",
    },
}
ALLOWED_RADIO_SERVICE_CODES = frozenset(
    {
        "PW",
        "YW",
        "GP",
        "YP",
        "GF",
        "YF",
        "GE",
        "YE",
        "SG",
        "SY",
        "IG",
        "YG",
        "IK",
        "YK",
        "GB",
        "YB",
        "GU",
        "YU",
        "GO",
        "YO",
        "GI",
        "YI",
        "GJ",
        "YJ",
        "GX",
        "YX",
        "GR",
        "YS",
        "GM",
        "YM",
        "GL",
        "YL",
        "QM",
        "IQ",
        "SL",
        "PA",
        "YC",
        "YD",
        "YH",
    }
)


class FccArchiveError(ValidationError):
    pass


@dataclass(frozen=True)
class ParsedFccArchive:
    dataset: str
    archive_name: str
    content_sha256: str
    structures: tuple[dict, ...] = ()
    licenses: tuple[dict, ...] = ()
    locations: tuple[dict, ...] = ()
    frequencies: tuple[dict, ...] = ()
    emissions: tuple[dict, ...] = ()
    record_counts: dict[str, int] = field(default_factory=dict)


def _value(fields: list[str], index: int) -> str:
    return fields[index].strip() if index < len(fields) else ""


def _date(value: str) -> date | None:
    if not value:
        return None
    try:
        month, day, year = (int(part) for part in value.split("/"))
        return date(year, month, day)
    except (TypeError, ValueError) as error:
        raise FccArchiveError(f"Invalid FCC date value: {value!r}.") from error


def _decimal(value: str) -> Decimal | None:
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation as error:
        raise FccArchiveError(f"Invalid FCC decimal value: {value!r}.") from error


def _integer(value: str) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError as error:
        raise FccArchiveError(f"Invalid FCC whole-number value: {value!r}.") from error


def _frequency_hz(value: str) -> int | None:
    frequency_mhz = _decimal(value)
    if frequency_mhz is None:
        return None
    frequency_hz = frequency_mhz * 1_000_000
    if frequency_hz != frequency_hz.to_integral_value():
        raise FccArchiveError(f"FCC frequency cannot be represented as integer hertz: {value!r}.")
    result = int(frequency_hz)
    if not 1 <= result <= 10_000_000_000:
        raise FccArchiveError(f"FCC frequency is outside the supported range: {value!r}.")
    return result


def _unique_records(records: list[dict]) -> list[dict]:
    unique = []
    seen = set()
    for record in records:
        identity = tuple(sorted(record.items()))
        if identity not in seen:
            seen.add(identity)
            unique.append(record)
    return unique


def _dms(
    degrees: str, minutes: str, seconds: str, direction: str, *, coordinate_type: str
) -> Decimal | None:
    if not any((degrees, minutes, seconds)):
        return None
    if not all((degrees, minutes, seconds, direction)):
        return None
    try:
        result = Decimal(degrees) + Decimal(minutes) / 60 + Decimal(seconds) / 3600
    except InvalidOperation:
        return None
    direction = direction.upper()
    valid_directions, negative_direction, maximum = {
        "latitude": ({"N", "S"}, "S", Decimal("90")),
        "longitude": ({"E", "W"}, "W", Decimal("180")),
    }[coordinate_type]
    if direction not in valid_directions:
        return None
    if direction == negative_direction:
        result = -result
    if not -maximum <= result <= maximum:
        return None
    return result.quantize(Decimal("0.0000001"))


def _coordinate_pair(latitude: Decimal | None, longitude: Decimal | None):
    if latitude is None or longitude is None:
        return None, None
    return latitude, longitude


def _archive_digest(path: Path, *, maximum: int) -> str:
    if not path.is_file():
        raise FccArchiveError(f"FCC archive does not exist: {path}.")
    if path.stat().st_size > maximum:
        raise FccArchiveError("FCC archive exceeds the configured compressed-size limit.")
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _validated_members(
    archive: zipfile.ZipFile, *, dataset: str, maximum_expanded_bytes: int
) -> dict[str, zipfile.ZipInfo]:
    members = archive.infolist()
    if not 1 <= len(members) <= MAX_MEMBERS:
        raise FccArchiveError("FCC archive member count is outside the supported range.")
    names: dict[str, zipfile.ZipInfo] = {}
    expanded_bytes = 0
    for member in members:
        path = PurePosixPath(member.filename.replace("\\", "/"))
        if member.is_dir() or path.is_absolute() or len(path.parts) != 1 or path.name in {"", "."}:
            raise FccArchiveError("FCC archive contains an unsafe member path.")
        if path.name in names:
            raise FccArchiveError("FCC archive contains duplicate member names.")
        if member.flag_bits & 0x1:
            raise FccArchiveError("Encrypted FCC archive members are not supported.")
        if member.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
            raise FccArchiveError("FCC archive uses an unsupported compression method.")
        if member.file_size > MAX_MEMBER_BYTES:
            raise FccArchiveError("FCC archive member exceeds the supported size limit.")
        expanded_bytes += member.file_size
        if expanded_bytes > maximum_expanded_bytes:
            raise FccArchiveError("FCC archive exceeds the configured expanded-size limit.")
        names[path.name] = member
    missing = REQUIRED_MEMBERS[dataset] - names.keys()
    if missing:
        raise FccArchiveError(
            f"FCC archive is missing required members: {', '.join(sorted(missing))}."
        )
    return names


def _rows(
    archive: zipfile.ZipFile,
    member: zipfile.ZipInfo,
    *,
    expected_record_type: str,
    maximum_records: int,
):
    count = 0
    with archive.open(member) as raw:
        text = io.TextIOWrapper(raw, encoding="latin-1", newline="")
        while True:
            line = text.readline(MAX_LINE_BYTES + 1)
            if not line:
                break
            if len(line.encode("latin-1")) > MAX_LINE_BYTES:
                raise FccArchiveError(f"{member.filename} contains an oversized row.")
            fields = line.rstrip("\r\n").split("|")
            if not fields or fields[0] != expected_record_type:
                raise FccArchiveError(f"{member.filename} contains an unexpected record type.")
            count += 1
            if count > maximum_records:
                raise FccArchiveError("FCC archive exceeds the configured record-count limit.")
            yield fields


def _parse_asr(archive: zipfile.ZipFile, members: dict[str, zipfile.ZipInfo], maximum: int):
    coordinates = {}
    for fields in _rows(
        archive, members["CO.dat"], expected_record_type="CO", maximum_records=maximum
    ):
        registration_number = _value(fields, 3)
        if registration_number and registration_number not in coordinates:
            coordinates[registration_number] = _coordinate_pair(
                _dms(
                    _value(fields, 6),
                    _value(fields, 7),
                    _value(fields, 8),
                    _value(fields, 9),
                    coordinate_type="latitude",
                ),
                _dms(
                    _value(fields, 11),
                    _value(fields, 12),
                    _value(fields, 13),
                    _value(fields, 14),
                    coordinate_type="longitude",
                ),
            )
    owners = {}
    for fields in _rows(
        archive, members["EN.dat"], expected_record_type="EN", maximum_records=maximum
    ):
        registration_number = _value(fields, 3)
        if registration_number and _value(fields, 5) == "O" and registration_number not in owners:
            owners[registration_number] = {
                "owner_name": _value(fields, 9),
                "owner_frn": _value(fields, 24),
            }
    structures = []
    for fields in _rows(
        archive, members["RA.dat"], expected_record_type="RA", maximum_records=maximum
    ):
        registration_number = _value(fields, 3)
        if not registration_number:
            raise FccArchiveError("ASR registration row is missing its registration number.")
        latitude, longitude = coordinates.get(registration_number, (None, None))
        structures.append(
            {
                "registration_number": registration_number,
                "unique_system_identifier": _value(fields, 4),
                "status_code": _value(fields, 8),
                **owners.get(registration_number, {"owner_name": "", "owner_frn": ""}),
                "structure_type": _value(fields, 32),
                "latitude": latitude,
                "longitude": longitude,
                "structure_height_m": _decimal(_value(fields, 28)),
                "ground_elevation_m": _decimal(_value(fields, 29)),
                "overall_height_m": _decimal(_value(fields, 30)),
                "overall_height_amsl_m": _decimal(_value(fields, 31)),
                "construction_date": _date(_value(fields, 33)),
                "faa_study_number": _value(fields, 34),
                "painting_lighting": _value(fields, 37),
                "dismantlement_date": _date(_value(fields, 43)),
            }
        )
    return structures


def _parse_uls(archive: zipfile.ZipFile, members: dict[str, zipfile.ZipInfo], maximum: int):
    entities = {}
    for fields in _rows(
        archive, members["EN.dat"], expected_record_type="EN", maximum_records=maximum
    ):
        unique_id = _value(fields, 1)
        if unique_id and _value(fields, 5) == "L" and unique_id not in entities:
            entities[unique_id] = fields

    licenses = []
    included_ids = set()
    for fields in _rows(
        archive, members["HD.dat"], expected_record_type="HD", maximum_records=maximum
    ):
        unique_id = _value(fields, 1)
        entity = entities.get(unique_id, [])
        service_code = _value(fields, 6)
        applicant_type = _value(entity, 23)
        if applicant_type == "G":
            selection_rule = "governmental_entity"
        elif service_code in ALLOWED_RADIO_SERVICE_CODES:
            selection_rule = "radio_service_allowlist_v1"
        else:
            continue
        if not unique_id or not _value(fields, 4):
            raise FccArchiveError(
                "Included ULS license is missing its source identifier or call sign."
            )
        included_ids.add(unique_id)
        licenses.append(
            {
                "unique_system_identifier": unique_id,
                "call_sign": _value(fields, 4),
                "license_status": _value(fields, 5),
                "radio_service_code": service_code,
                "applicant_type_code": applicant_type,
                "selection_rule": selection_rule,
                "licensee_name": _value(entity, 7),
                "frn": _value(entity, 22),
                "address": _value(entity, 15),
                "city": _value(entity, 16),
                "state": _value(entity, 17),
                "postal_code": _value(entity, 18),
                "grant_date": _date(_value(fields, 7)),
                "expiration_date": _date(_value(fields, 8)),
                "cancellation_date": _date(_value(fields, 9)),
                "last_action_date": _date(_value(fields, 43)),
            }
        )

    locations = []
    for fields in _rows(
        archive, members["LO.dat"], expected_record_type="LO", maximum_records=maximum
    ):
        unique_id = _value(fields, 1)
        location_number = _integer(_value(fields, 8))
        if unique_id not in included_ids or location_number is None:
            continue
        latitude, longitude = _coordinate_pair(
            _dms(
                _value(fields, 19),
                _value(fields, 20),
                _value(fields, 21),
                _value(fields, 22),
                coordinate_type="latitude",
            ),
            _dms(
                _value(fields, 23),
                _value(fields, 24),
                _value(fields, 25),
                _value(fields, 26),
                coordinate_type="longitude",
            ),
        )
        locations.append(
            {
                "license_source_id": unique_id,
                "location_number": location_number,
                "location_type_code": _value(fields, 6),
                "location_class_code": _value(fields, 7),
                "address": _value(fields, 11),
                "city": _value(fields, 12),
                "county": _value(fields, 13),
                "state": _value(fields, 14),
                "latitude": latitude,
                "longitude": longitude,
                "ground_elevation_m": _decimal(_value(fields, 38)),
                "asr_registration_number": _value(fields, 37),
                "structure_type": _value(fields, 40),
            }
        )

    frequencies = []
    for fields in _rows(
        archive, members["FR.dat"], expected_record_type="FR", maximum_records=maximum
    ):
        unique_id = _value(fields, 1)
        frequency_hz = _frequency_hz(_value(fields, 10))
        location_number = _integer(_value(fields, 6))
        antenna_number = _integer(_value(fields, 7))
        if (
            unique_id not in included_ids
            or frequency_hz is None
            or location_number is None
            or antenna_number is None
        ):
            continue
        frequencies.append(
            {
                "license_source_id": unique_id,
                "location_number": location_number,
                "antenna_number": antenna_number,
                "station_class_code": _value(fields, 8),
                "frequency_hz": frequency_hz,
                "output_power_w": _decimal(_value(fields, 15)),
                "effective_radiated_power_w": _decimal(_value(fields, 16)),
                "number_of_units": _integer(_value(fields, 24)),
                "source_frequency_id": _value(fields, 26),
            }
        )

    emissions = []
    for fields in _rows(
        archive, members["EM.dat"], expected_record_type="EM", maximum_records=maximum
    ):
        unique_id = _value(fields, 1)
        frequency_hz = _frequency_hz(_value(fields, 7))
        location_number = _integer(_value(fields, 5))
        antenna_number = _integer(_value(fields, 6))
        designator = _value(fields, 9)
        if (
            unique_id not in included_ids
            or frequency_hz is None
            or location_number is None
            or antenna_number is None
            or not designator
        ):
            continue
        emissions.append(
            {
                "license_source_id": unique_id,
                "location_number": location_number,
                "antenna_number": antenna_number,
                "frequency_hz": frequency_hz,
                "emission_designator": designator,
                "source_frequency_id": _value(fields, 15),
            }
        )
    return licenses, locations, _unique_records(frequencies), _unique_records(emissions)


def parse_fcc_archive(
    path: str | Path,
    *,
    dataset: str,
    maximum_archive_bytes: int = MAX_ARCHIVE_BYTES,
    maximum_expanded_bytes: int = MAX_EXPANDED_BYTES,
    maximum_records: int = MAX_RECORDS,
) -> ParsedFccArchive:
    if dataset not in EXPECTED_ARCHIVES:
        raise FccArchiveError(f"Unsupported FCC dataset: {dataset!r}.")
    archive_path = Path(path)
    expected_name = EXPECTED_ARCHIVES[dataset]
    if archive_path.name != expected_name:
        raise FccArchiveError(f"{dataset} requires an archive named {expected_name}.")
    digest = _archive_digest(archive_path, maximum=maximum_archive_bytes)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = _validated_members(
                archive, dataset=dataset, maximum_expanded_bytes=maximum_expanded_bytes
            )
            if dataset == FccImportBatch.Dataset.ASR:
                structures = _parse_asr(archive, members, maximum_records)
                return ParsedFccArchive(
                    dataset=dataset,
                    archive_name=archive_path.name,
                    content_sha256=digest,
                    structures=tuple(structures),
                    record_counts={"antenna_structures": len(structures)},
                )
            licenses, locations, frequencies, emissions = _parse_uls(
                archive, members, maximum_records
            )
            return ParsedFccArchive(
                dataset=dataset,
                archive_name=archive_path.name,
                content_sha256=digest,
                licenses=tuple(licenses),
                locations=tuple(locations),
                frequencies=tuple(frequencies),
                emissions=tuple(emissions),
                record_counts={
                    "licenses": len(licenses),
                    "locations": len(locations),
                    "frequencies": len(frequencies),
                    "emissions": len(emissions),
                },
            )
    except zipfile.BadZipFile as error:
        raise FccArchiveError("FCC archive is not a valid ZIP file.") from error
