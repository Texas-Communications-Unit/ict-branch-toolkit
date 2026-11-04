import sqlite3
import tracemalloc
import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.fcc_data import services, spool
from apps.fcc_data.spool import FccSpoolError, private_record_spool


def test_spool_preserves_types_order_and_numeric_deduplication():
    with private_record_spool() as store:
        directory = store.directory
        records = store.records("frequencies")
        first = {"text": "value|with\nseparators", "number": Decimal("1.00"), "empty": None}
        records.append(first)
        records.append({**first, "number": Decimal("1.0")})
        second = {"integer": 155752500, "date": date(2026, 11, 4), "signed": -10}
        records.append(second)
        assert len(records) == 2
        assert list(records) == [first, second]
        assert list(records) == [first, second]
        assert isinstance(list(records)[0]["number"], Decimal)
        assert list(records)[0]["number"].as_tuple() == first["number"].as_tuple()
        assert directory.exists()
    assert not directory.exists()


def test_spool_removes_private_storage_after_failure():
    with pytest.raises(RuntimeError, match="synthetic failure"):
        with private_record_spool() as store:
            directory = store.directory
            store.records("locations").append({"state": "TX"})
            raise RuntimeError("synthetic failure")
    assert not directory.exists()


def test_spool_keeps_extreme_decimal_exponents_compact():
    with private_record_spool() as store:
        records = store.records("frequencies")
        value = Decimal("1E+1000000")
        records.append({"value": value})
        assert list(records) == [{"value": value}]
        assert len(spool._encode({"value": value})) < 100
        precise = Decimal("123456789012345678901234567890.123456789")
        records.append({"value": precise})
        assert list(records)[1]["value"].as_tuple() == precise.as_tuple()


def test_spool_uses_only_its_private_child_of_selected_work_directory(tmp_path):
    archive = tmp_path / "synthetic.zip"
    archive.write_bytes(b"synthetic archive")
    with private_record_spool(directory=tmp_path) as store:
        child = store.directory
        assert child.parent == tmp_path
        store.records("locations").append({"value": 1})
    assert not child.exists()
    assert archive.read_bytes() == b"synthetic archive"


def test_spool_capacity_guard_cleans_storage():
    with pytest.raises((FccSpoolError, sqlite3.DatabaseError)):
        with private_record_spool(maximum_bytes=65536) as store:
            directory = store.directory
            records = store.records("emissions")
            for value in range(2000):
                records.append({"value": value})
    assert not directory.exists()


def test_spool_reserves_free_disk_space(monkeypatch):
    monkeypatch.setattr(spool.shutil, "disk_usage", lambda path: SimpleNamespace(free=0))
    with pytest.raises(FccSpoolError, match="capacity limit"):
        with private_record_spool():
            pytest.fail("Low-capacity storage must not become usable")


def test_spool_refuses_nonfinite_decimals_and_untrusted_collection_names():
    with private_record_spool() as store:
        with pytest.raises(FccSpoolError, match="Unsupported FCC spool collection"):
            store.records('frequencies"; DROP TABLE anything; --')
        records = store.records("frequencies")
        with pytest.raises(FccSpoolError, match="non-finite"):
            records.append({"power": Decimal("NaN")})
        assert len(records) == 0


def test_spool_digest_collision_never_silently_drops_a_record(monkeypatch):
    monkeypatch.setattr(
        spool.hashlib, "sha256", lambda data: SimpleNamespace(digest=lambda: b"0" * 32)
    )
    with private_record_spool() as store:
        records = store.records("locations")
        records.append({"value": "first"})
        with pytest.raises(FccSpoolError, match="identity collision"):
            records.append({"value": "different"})
        assert len(records) == 1


def test_large_spool_does_not_retain_related_payloads_in_python_memory():
    with private_record_spool() as store:
        records = store.records("emissions")
        tracemalloc.start()
        try:
            for value in range(15000):
                records.append({"sequence": value, "payload": "x" * 1024})
            read_count = sum(len(chunk) for chunk in services._chunks(records, size=11))
            _current, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        assert read_count == 15000
        # The input exceeds 15 MB, whereas iteration and parsing retain bounded batches.
        assert peak < 5 * 1024**2


def test_bulk_insert_keeps_uuid4_identifiers_ordered_across_chunks(monkeypatch):
    identifiers = [uuid.uuid4() for _ in range(5)]
    source = iter(sorted(identifiers, reverse=True))
    monkeypatch.setattr(services.uuid, "uuid4", lambda: next(source))
    monkeypatch.setattr(services, "IMPORT_BATCH_SIZE", 2)
    batches = []
    progress = []
    model = SimpleNamespace(
        _meta=SimpleNamespace(model_name="synthetic"),
        objects=SimpleNamespace(bulk_create=lambda objects, **kwargs: batches.append(objects)),
    )
    services._bulk_create(
        model,
        tuple({"value": value} for value in range(5)),
        lambda record, identifier: SimpleNamespace(id=identifier, **record),
        lambda *values: progress.append(values),
    )
    assert [len(batch) for batch in batches] == [2, 2, 1]
    saved = [item for batch in batches for item in batch]
    assert [item.id for item in saved] == sorted(identifiers)
    assert all(item.id.version == 4 for item in saved)
    assert [item.value for item in saved] == list(range(5))
    assert progress == [("synthetic", 0, 5), ("synthetic", 5, 5)]
