"""Private, disposable storage for large parsed FCC related-record collections."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

MAX_SPOOL_BYTES = 20 * 1024**3
RESERVE_BYTES = 2 * 1024**3
COLLECTIONS = frozenset({"locations", "frequencies", "emissions"})


class FccSpoolError(ValueError):
    pass


def _encode(record: dict, *, canonical=False) -> str:
    values = {}
    for key, value in record.items():
        if isinstance(value, Decimal):
            if not value.is_finite():
                raise FccSpoolError("FCC related records contain a non-finite decimal value.")
            sign, digits, exponent = value.as_tuple()
            digits = list(digits)
            if canonical and value == 0:
                sign, digits, exponent = 0, [0], 0
            elif canonical:
                while digits[-1] == 0:
                    digits.pop()
                    exponent += 1
            # Do not expand scientific notation: a short input may have a huge exponent.
            values[key] = ["decimal", [sign, digits, exponent]]
        elif type(value) is date:
            values[key] = ["date", value.isoformat()]
        elif type(value) in (str, int, bool, type(None)):
            values[key] = ["value", value]
        else:
            raise FccSpoolError("Unsupported FCC related-record value type.")
    return json.dumps(values, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _decode(payload: str) -> dict:
    converters = {
        "decimal": lambda value: Decimal((value[0], tuple(value[1]), value[2])),
        "date": date.fromisoformat,
        "value": lambda value: value,
    }
    return {key: converters[tag](value) for key, (tag, value) in json.loads(payload).items()}


class SpoolRecords:
    def __init__(self, store: RecordSpool, name: str):
        if name not in COLLECTIONS:
            raise FccSpoolError("Unsupported FCC spool collection.")
        self.store = store
        self.name = name
        self.count = 0
        # The identifier is selected exclusively from COLLECTIONS, never archive input.
        store.connection.execute(
            f'CREATE TABLE "{name}" (sequence INTEGER PRIMARY KEY, '
            "digest BLOB UNIQUE NOT NULL, payload TEXT NOT NULL)"
        )

    def append(self, record: dict) -> None:
        payload = _encode(record)
        identity = _encode(record, canonical=True)
        digest = hashlib.sha256(identity.encode("ascii")).digest()
        cursor = self.store.connection.execute(
            f'INSERT OR IGNORE INTO "{self.name}" (digest, payload) VALUES (?, ?)',
            (digest, payload),
        )
        if cursor.rowcount:
            self.count += 1
        else:
            existing = self.store.connection.execute(
                f'SELECT payload FROM "{self.name}" WHERE digest = ?', (digest,)
            ).fetchone()[0]
            if _decode(existing) != record:
                raise FccSpoolError("FCC spool identity collision; import refused.")
        self.store.writes += 1
        if self.store.writes % 1000 == 0:
            self.store.check_capacity()

    def __len__(self) -> int:
        return self.count

    def __iter__(self) -> Iterator[dict]:
        cursor = self.store.connection.execute(
            f'SELECT payload FROM "{self.name}" ORDER BY sequence'
        )
        try:
            while rows := cursor.fetchmany(1000):
                for (payload,) in rows:
                    yield _decode(payload)
        finally:
            cursor.close()


class RecordSpool:
    def __init__(self, connection, directory: Path, *, maximum_bytes=MAX_SPOOL_BYTES):
        self.connection = connection
        self.directory = directory
        self.maximum_bytes = maximum_bytes
        self.writes = 0
        self.collections: dict[str, SpoolRecords] = {}
        self.check_capacity()

    def records(self, name: str) -> SpoolRecords:
        if name not in self.collections:
            self.collections[name] = SpoolRecords(self, name)
        return self.collections[name]

    def check_capacity(self) -> None:
        size = sum(path.stat().st_size for path in self.directory.iterdir() if path.is_file())
        if size >= self.maximum_bytes or shutil.disk_usage(self.directory).free < RESERVE_BYTES:
            raise FccSpoolError("FCC temporary parsing storage capacity limit reached.")


@contextmanager
def private_record_spool(*, maximum_bytes=MAX_SPOOL_BYTES, directory=None):
    with TemporaryDirectory(prefix="ict-fcc-parsed-", dir=directory) as directory:
        path = Path(directory) / "records.sqlite3"
        with closing(sqlite3.connect(path)) as connection:
            path.chmod(0o600)
            # This database is disposable and never a recovery or trusted-input artifact.
            # A failed process discards it; no application transaction relies on its durability.
            connection.execute("PRAGMA journal_mode=OFF")
            connection.execute("PRAGMA synchronous=OFF")
            connection.execute("PRAGMA cache_size=-32768")
            connection.execute("PRAGMA temp_store=FILE")
            page_size = connection.execute("PRAGMA page_size").fetchone()[0]
            if type(maximum_bytes) is not int or maximum_bytes < page_size:
                raise FccSpoolError("FCC temporary parsing storage capacity limit reached.")
            connection.execute(f"PRAGMA max_page_count={maximum_bytes // page_size}")
            yield RecordSpool(connection, Path(directory), maximum_bytes=maximum_bytes)
