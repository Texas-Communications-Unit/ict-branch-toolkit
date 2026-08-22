import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.accounts.models import Role, UserRoleAssignment
from apps.fcc_data.models import (
    AntennaStructure,
    FccImportBatch,
    UlsEmission,
    UlsFrequency,
    UlsLicense,
    UlsLocation,
)
from apps.fcc_data.parser import (
    FccArchiveError,
    _frequency_hz,
    _unique_records,
    parse_fcc_archive,
)
from apps.fcc_data.services import apply_complete_archive


def _row(size, values):
    fields = [""] * size
    for index, value in values.items():
        fields[index] = str(value)
    return "|".join(fields)


def _write_zip(path: Path, members: dict[str, list[str] | str]):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, rows in members.items():
            content = rows if isinstance(rows, str) else "\n".join(rows) + "\n"
            archive.writestr(name, content)


def _asr_archive(path: Path):
    _write_zip(
        path,
        {
            "RA.dat": [
                _row(
                    49,
                    {
                        0: "RA",
                        1: "REG",
                        3: "1234567",
                        4: "7654321",
                        8: "A",
                        28: "75.5",
                        29: "200.0",
                        30: "80.0",
                        31: "280.0",
                        32: "GTOWER",
                        33: "01/02/2020",
                        34: "2020-ASW-1234-OE",
                        37: "1,3,6,13",
                    },
                )
            ],
            "CO.dat": [
                _row(
                    18,
                    {
                        0: "CO",
                        1: "REG",
                        3: "1234567",
                        4: "7654321",
                        6: "33",
                        7: "12",
                        8: "30.0",
                        9: "N",
                        11: "97",
                        12: "8",
                        13: "15.0",
                        14: "W",
                    },
                )
            ],
            "EN.dat": [
                _row(
                    25,
                    {
                        0: "EN",
                        1: "REG",
                        3: "1234567",
                        4: "7654321",
                        5: "O",
                        9: "Synthetic Tower Owner",
                        24: "0000000001",
                    },
                )
            ],
        },
    )


def _uls_archive(path: Path):
    headers = [
        _row(
            59,
            {
                0: "HD",
                1: "1001",
                4: "WQGOV1",
                5: "A",
                6: "ZZ",
                7: "01/02/2020",
                8: "01/02/2030",
                43: "02/03/2026",
            },
        ),
        _row(59, {0: "HD", 1: "1002", 4: "WQBUS1", 5: "A", 6: "IG"}),
        _row(59, {0: "HD", 1: "1003", 4: "WQHAM1", 5: "A", 6: "HA"}),
    ]
    entities = [
        _row(
            30,
            {
                0: "EN",
                1: unique_id,
                5: "L",
                7: name,
                15: "100 Synthetic Way",
                16: "Denton",
                17: "TX",
                18: "76201",
                22: frn,
                23: applicant_type,
            },
        )
        for unique_id, name, frn, applicant_type in (
            ("1001", "Synthetic County", "0000000001", "G"),
            ("1002", "Synthetic Radio Company", "0000000002", "C"),
            ("1003", "Synthetic Amateur", "0000000003", "I"),
        )
    ]
    locations = [
        _row(
            51,
            {
                0: "LO",
                1: unique_id,
                6: "F",
                7: "T",
                8: "1",
                11: "200 Synthetic Road",
                12: "Denton",
                13: "Denton",
                14: "TX",
                19: "33",
                20: "12",
                21: "30.0",
                22: "N",
                23: "97",
                24: "8",
                25: "15.0",
                26: "W",
                37: "1234567",
                38: "200.0",
                40: "GTOWER",
            },
        )
        for unique_id in ("1001", "1002", "1003")
    ]
    direction_only = locations[1].split("|")
    direction_only[19:27] = ["", "", "", "N", "", "", "", "W"]
    locations[1] = "|".join(direction_only)
    frequencies = [
        _row(
            30,
            {
                0: "FR",
                1: unique_id,
                6: "1",
                7: "1",
                8: "FB2",
                10: frequency,
                15: "50.0",
                16: "100.0",
                24: "25",
                26: "1",
            },
        )
        for unique_id, frequency in (
            ("1001", "155.75250000"),
            ("1002", "451.01250000"),
            ("1003", "146.52000000"),
        )
    ]
    emissions = [
        _row(
            16,
            {
                0: "EM",
                1: unique_id,
                5: "1",
                6: "1",
                7: frequency,
                9: "11K2F3E",
                15: "1",
            },
        )
        for unique_id, frequency in (
            ("1001", "155.75250000"),
            ("1002", "451.01250000"),
            ("1003", "146.52000000"),
        )
    ]
    _write_zip(
        path,
        {
            "HD.dat": headers,
            "EN.dat": entities,
            "LO.dat": locations,
            "FR.dat": frequencies,
            "EM.dat": emissions,
        },
    )


def test_parse_asr_complete_archive(tmp_path):
    archive = tmp_path / "r_tower.zip"
    _asr_archive(archive)

    parsed = parse_fcc_archive(archive, dataset=FccImportBatch.Dataset.ASR)

    assert parsed.record_counts == {"antenna_structures": 1}
    structure = parsed.structures[0]
    assert structure["registration_number"] == "1234567"
    assert structure["owner_name"] == "Synthetic Tower Owner"
    assert str(structure["latitude"]) == "33.2083333"
    assert str(structure["longitude"]) == "-97.1375000"


def test_parse_asr_retains_structure_with_incomplete_coordinate_as_unknown(tmp_path):
    archive = tmp_path / "r_tower.zip"
    _asr_archive(archive)
    with zipfile.ZipFile(archive, "r") as source:
        members = {name: source.read(name).decode("latin-1") for name in source.namelist()}
    coordinate = members["CO.dat"].split("|")
    coordinate[8] = ""
    members["CO.dat"] = "|".join(coordinate)
    _write_zip(archive, members)

    parsed = parse_fcc_archive(archive, dataset=FccImportBatch.Dataset.ASR)

    assert parsed.record_counts == {"antenna_structures": 1}
    assert parsed.structures[0]["latitude"] is None
    assert parsed.structures[0]["longitude"] is None


def test_parse_uls_selects_government_and_two_way_services(tmp_path):
    archive = tmp_path / "l_LMpriv.zip"
    _uls_archive(archive)

    parsed = parse_fcc_archive(archive, dataset=FccImportBatch.Dataset.ULS_PRIVATE)

    assert [record["call_sign"] for record in parsed.licenses] == ["WQGOV1", "WQBUS1"]
    assert parsed.licenses[0]["selection_rule"] == "governmental_entity"
    assert parsed.licenses[1]["selection_rule"] == "radio_service_allowlist_v1"
    assert parsed.locations[1]["latitude"] is None
    assert parsed.locations[1]["longitude"] is None
    assert [record["frequency_hz"] for record in parsed.frequencies] == [155752500, 451012500]
    assert parsed.record_counts == {
        "licenses": 2,
        "locations": 2,
        "frequencies": 2,
        "emissions": 2,
    }


def test_parse_uls_treats_invalid_axis_direction_as_unknown(tmp_path):
    archive = tmp_path / "l_LMpriv.zip"
    _uls_archive(archive)
    with zipfile.ZipFile(archive, "r") as source:
        members = {name: source.read(name).decode("latin-1") for name in source.namelist()}
    locations = members["LO.dat"].splitlines()
    first_location = locations[0].split("|")
    first_location[26] = "2"
    locations[0] = "|".join(first_location)
    members["LO.dat"] = "\n".join(locations) + "\n"
    _write_zip(archive, members)

    parsed = parse_fcc_archive(archive, dataset=FccImportBatch.Dataset.ULS_PRIVATE)

    assert parsed.locations[0]["latitude"] is None
    assert parsed.locations[0]["longitude"] is None


def test_parse_uls_does_not_validate_frequencies_for_excluded_services(tmp_path):
    archive = tmp_path / "l_LMpriv.zip"
    _uls_archive(archive)
    with zipfile.ZipFile(archive, "r") as source:
        members = {name: source.read(name).decode("latin-1") for name in source.namelist()}
    frequency_rows = members["FR.dat"].splitlines()
    excluded_frequency = frequency_rows[2].split("|")
    excluded_frequency[10] = "24150.00000000"
    frequency_rows[2] = "|".join(excluded_frequency)
    members["FR.dat"] = "\n".join(frequency_rows) + "\n"
    emission_rows = members["EM.dat"].splitlines()
    excluded_emission = emission_rows[2].split("|")
    excluded_emission[7] = "24150.00000000"
    emission_rows[2] = "|".join(excluded_emission)
    members["EM.dat"] = "\n".join(emission_rows) + "\n"
    _write_zip(archive, members)

    parsed = parse_fcc_archive(archive, dataset=FccImportBatch.Dataset.ULS_PRIVATE)

    assert [record["frequency_hz"] for record in parsed.frequencies] == [155752500, 451012500]
    assert [record["frequency_hz"] for record in parsed.emissions] == [155752500, 451012500]


def test_parse_uls_supports_included_radiolocation_frequency(tmp_path):
    archive = tmp_path / "l_LMpriv.zip"
    _uls_archive(archive)
    with zipfile.ZipFile(archive, "r") as source:
        members = {name: source.read(name).decode("latin-1") for name in source.namelist()}
    frequency_rows = members["FR.dat"].splitlines()
    included_frequency = frequency_rows[0].split("|")
    included_frequency[10] = "24150.00000000"
    frequency_rows[0] = "|".join(included_frequency)
    members["FR.dat"] = "\n".join(frequency_rows) + "\n"
    emission_rows = members["EM.dat"].splitlines()
    included_emission = emission_rows[0].split("|")
    included_emission[7] = "24150.00000000"
    emission_rows[0] = "|".join(included_emission)
    members["EM.dat"] = "\n".join(emission_rows) + "\n"
    _write_zip(archive, members)

    parsed = parse_fcc_archive(archive, dataset=FccImportBatch.Dataset.ULS_PRIVATE)

    assert parsed.frequencies[0]["frequency_hz"] == 24_150_000_000
    assert parsed.emissions[0]["frequency_hz"] == 24_150_000_000


@pytest.mark.django_db
def test_parse_and_apply_uls_preserves_signed_fcc_source_values(tmp_path):
    archive = tmp_path / "l_LMpriv.zip"
    _uls_archive(archive)
    with zipfile.ZipFile(archive, "r") as source:
        members = {name: source.read(name).decode("latin-1") for name in source.namelist()}
    frequency_rows = members["FR.dat"].splitlines()
    signed_frequency = frequency_rows[0].split("|")
    signed_frequency[7] = "-10"
    signed_frequency[24] = "-1"
    frequency_rows[0] = "|".join(signed_frequency)
    members["FR.dat"] = "\n".join(frequency_rows) + "\n"
    emission_rows = members["EM.dat"].splitlines()
    signed_emission = emission_rows[0].split("|")
    signed_emission[6] = "-10"
    emission_rows[0] = "|".join(signed_emission)
    members["EM.dat"] = "\n".join(emission_rows) + "\n"
    _write_zip(archive, members)

    parsed = parse_fcc_archive(archive, dataset=FccImportBatch.Dataset.ULS_PRIVATE)
    actor = get_user_model().objects.create_user(username="fcc-sentinel-admin", password="unused")
    UserRoleAssignment.objects.create(user=actor, role=Role.ADMINISTRATOR, assigned_by=actor)
    apply_complete_archive(
        parsed=parsed,
        source_url="https://data.fcc.gov/download/pub/uls/complete/l_LMpriv.zip",
        retrieved_at=datetime(2026, 8, 22, tzinfo=UTC),
        actor=actor,
    )

    frequency = UlsFrequency.objects.get(license__unique_system_identifier="1001")
    emission = UlsEmission.objects.get(license__unique_system_identifier="1001")
    assert (frequency.antenna_number, frequency.number_of_units) == (-10, -1)
    assert emission.antenna_number == -10


def test_parse_uls_repairs_unescaped_entity_delimiters(tmp_path):
    archive = tmp_path / "l_LMpriv.zip"
    _uls_archive(archive)
    with zipfile.ZipFile(archive, "r") as source:
        members = {name: source.read(name).decode("latin-1") for name in source.namelist()}
    entity_rows = members["EN.dat"].splitlines()
    entity_rows[0] = entity_rows[0].replace("Synthetic County", "Synthetic | County")
    contact_fields = entity_rows[1].split("|")
    contact_fields[20] = "Director"
    contact_fields.insert(21, "Facilities")
    entity_rows[1] = "|".join(contact_fields)
    members["EN.dat"] = "\n".join(entity_rows) + "\n"
    _write_zip(archive, members)

    parsed = parse_fcc_archive(archive, dataset=FccImportBatch.Dataset.ULS_PRIVATE)

    assert parsed.licenses[0]["licensee_name"] == "Synthetic | County"
    assert parsed.licenses[0]["applicant_type_code"] == "G"
    assert parsed.licenses[0]["frn"] == "0000000001"
    assert parsed.licenses[1]["applicant_type_code"] == "C"
    assert parsed.licenses[1]["frn"] == "0000000002"


def test_parse_uls_skips_zero_frequency_placeholders(tmp_path):
    archive = tmp_path / "l_LMpriv.zip"
    _uls_archive(archive)
    with zipfile.ZipFile(archive, "r") as source:
        members = {name: source.read(name).decode("latin-1") for name in source.namelist()}
    frequency_rows = members["FR.dat"].splitlines()
    included_frequency = frequency_rows[0].split("|")
    included_frequency[10] = ".00000000"
    frequency_rows[0] = "|".join(included_frequency)
    members["FR.dat"] = "\n".join(frequency_rows) + "\n"
    emission_rows = members["EM.dat"].splitlines()
    included_emission = emission_rows[0].split("|")
    included_emission[7] = ".00000000"
    emission_rows[0] = "|".join(included_emission)
    members["EM.dat"] = "\n".join(emission_rows) + "\n"
    _write_zip(archive, members)

    parsed = parse_fcc_archive(archive, dataset=FccImportBatch.Dataset.ULS_PRIVATE)

    assert [record["frequency_hz"] for record in parsed.frequencies] == [451012500]
    assert [record["frequency_hz"] for record in parsed.emissions] == [451012500]


def test_frequency_conversion_rounds_subhertz_source_precision():
    assert _frequency_hz("486.73750007") == 486_737_500
    assert _frequency_hz("486.73750050") == 486_737_501
    assert _frequency_hz("486.73750051") == 486_737_501


def test_duplicate_filter_reuses_the_large_source_list():
    records = [{"value": 1}, {"value": 2}, {"value": 1}]

    result = _unique_records(records)

    assert result is records
    assert result == [{"value": 1}, {"value": 2}]


def test_parse_uls_deduplicates_exact_locations_and_retains_reused_location_numbers(tmp_path):
    archive = tmp_path / "l_LMpriv.zip"
    _uls_archive(archive)
    with zipfile.ZipFile(archive, "r") as source:
        members = {name: source.read(name).decode("latin-1") for name in source.namelist()}
    location_rows = members["LO.dat"].splitlines()
    conflicting_location = location_rows[0].split("|")
    conflicting_location[12] = "Lewisville"
    conflicting_location[19:27] = ["33", "2", "48.0", "N", "96", "59", "42.0", "W"]
    members["LO.dat"] = (
        "\n".join([*location_rows, location_rows[0], "|".join(conflicting_location)]) + "\n"
    )
    _write_zip(archive, members)

    parsed = parse_fcc_archive(archive, dataset=FccImportBatch.Dataset.ULS_PRIVATE)

    government_locations = [
        location
        for location in parsed.locations
        if location["license_source_id"] == "1001" and location["location_number"] == 1
    ]
    assert len(government_locations) == 2
    assert [location["city"] for location in government_locations] == ["Denton", "Lewisville"]


@pytest.mark.django_db
def test_apply_complete_archive_accepts_reused_location_numbers(tmp_path):
    archive = tmp_path / "l_LMpriv.zip"
    _uls_archive(archive)
    with zipfile.ZipFile(archive, "r") as source:
        members = {name: source.read(name).decode("latin-1") for name in source.namelist()}
    location_rows = members["LO.dat"].splitlines()
    additional_location = location_rows[0].split("|")
    additional_location[12] = "Lewisville"
    members["LO.dat"] = "\n".join([*location_rows, "|".join(additional_location)]) + "\n"
    _write_zip(archive, members)
    parsed = parse_fcc_archive(archive, dataset=FccImportBatch.Dataset.ULS_PRIVATE)
    actor = get_user_model().objects.create_user(username="fcc-location-admin", password="unused")
    UserRoleAssignment.objects.create(user=actor, role=Role.ADMINISTRATOR, assigned_by=actor)

    apply_complete_archive(
        parsed=parsed,
        source_url="https://data.fcc.gov/download/pub/uls/complete/l_LMpriv.zip",
        retrieved_at=datetime(2026, 8, 22, tzinfo=UTC),
        actor=actor,
    )

    license_record = UlsLicense.objects.get(unique_system_identifier="1001")
    assert list(
        UlsLocation.objects.filter(license=license_record, location_number=1)
        .order_by("city")
        .values_list("city", flat=True)
    ) == ["Denton", "Lewisville"]


def test_parser_rejects_wrong_name_and_unsafe_member(tmp_path):
    wrong_name = tmp_path / "amateur.zip"
    _uls_archive(wrong_name)
    with pytest.raises(FccArchiveError, match="requires an archive named"):
        parse_fcc_archive(wrong_name, dataset=FccImportBatch.Dataset.ULS_PRIVATE)

    unsafe = tmp_path / "r_tower.zip"
    _write_zip(unsafe, {"../RA.dat": "RA|", "CO.dat": "CO|", "EN.dat": "EN|"})
    with pytest.raises(FccArchiveError, match="unsafe member path"):
        parse_fcc_archive(unsafe, dataset=FccImportBatch.Dataset.ASR)


def test_parser_enforces_expanded_size_limit(tmp_path):
    archive = tmp_path / "r_tower.zip"
    _asr_archive(archive)
    with pytest.raises(FccArchiveError, match="expanded-size limit"):
        parse_fcc_archive(
            archive,
            dataset=FccImportBatch.Dataset.ASR,
            maximum_expanded_bytes=10,
        )


@pytest.mark.django_db
def test_apply_complete_archive_is_atomic_current_and_idempotent(tmp_path):
    archive = tmp_path / "l_LMpriv.zip"
    _uls_archive(archive)
    parsed = parse_fcc_archive(archive, dataset=FccImportBatch.Dataset.ULS_PRIVATE)
    actor = get_user_model().objects.create_user(username="fcc-admin", password="unused-test")
    UserRoleAssignment.objects.create(user=actor, role=Role.ADMINISTRATOR, assigned_by=actor)

    batch, created = apply_complete_archive(
        parsed=parsed,
        source_url="https://data.fcc.gov/download/pub/uls/complete/l_LMpriv.zip",
        retrieved_at=datetime(2026, 8, 21, tzinfo=UTC),
        actor=actor,
    )
    duplicate, duplicate_created = apply_complete_archive(
        parsed=parsed,
        source_url="https://data.fcc.gov/download/pub/uls/complete/l_LMpriv.zip",
        retrieved_at=datetime(2026, 8, 21, tzinfo=UTC),
        actor=actor,
    )

    assert created is True
    assert duplicate_created is False
    assert duplicate == batch
    assert FccImportBatch.objects.count() == 1
    assert UlsLicense.objects.count() == 2
    assert UlsLocation.objects.count() == 2
    assert UlsFrequency.objects.count() == 2
    assert UlsEmission.objects.count() == 2


@pytest.mark.django_db
def test_apply_complete_archive_bounds_bulk_insert_memory(tmp_path, monkeypatch):
    from django.db.models.query import QuerySet

    from apps.fcc_data import services

    archive = tmp_path / "l_LMpriv.zip"
    _uls_archive(archive)
    parsed = parse_fcc_archive(archive, dataset=FccImportBatch.Dataset.ULS_PRIVATE)
    actor = get_user_model().objects.create_user(username="fcc-batch-admin", password="unused")
    UserRoleAssignment.objects.create(user=actor, role=Role.ADMINISTRATOR, assigned_by=actor)
    original_bulk_create = QuerySet.bulk_create
    fcc_batch_sizes = []

    def tracking_bulk_create(queryset, objects, **kwargs):
        if queryset.model._meta.app_label == "fcc_data":
            fcc_batch_sizes.append(len(objects))
        return original_bulk_create(queryset, objects, **kwargs)

    monkeypatch.setattr(services, "IMPORT_BATCH_SIZE", 1)
    monkeypatch.setattr(QuerySet, "bulk_create", tracking_bulk_create)

    apply_complete_archive(
        parsed=parsed,
        source_url="https://data.fcc.gov/download/pub/uls/complete/l_LMpriv.zip",
        retrieved_at=datetime(2026, 8, 21, tzinfo=UTC),
        actor=actor,
    )

    assert fcc_batch_sizes
    assert max(fcc_batch_sizes) == 1


@pytest.mark.django_db
def test_management_command_dry_run_then_apply(tmp_path, capsys):
    archive = tmp_path / "r_tower.zip"
    _asr_archive(archive)
    actor = get_user_model().objects.create_user(username="fcc-admin", password="unused-test")
    UserRoleAssignment.objects.create(user=actor, role=Role.ADMINISTRATOR, assigned_by=actor)
    source_url = "https://data.fcc.gov/download/pub/uls/complete/r_tower.zip"

    call_command(
        "import_fcc_archive",
        archive,
        dataset="asr",
        source_url=source_url,
    )
    assert FccImportBatch.objects.count() == 0

    call_command(
        "import_fcc_archive",
        archive,
        dataset="asr",
        source_url=source_url,
        apply=True,
        username=actor.username,
    )
    assert FccImportBatch.objects.count() == 1
    assert AntennaStructure.objects.count() == 1
    assert "No data was written" in capsys.readouterr().out
