from __future__ import annotations

import uuid
from itertools import islice

from django.db import transaction

from apps.audit.services import record_event

from .models import (
    AntennaStructure,
    FccImportBatch,
    UlsEmission,
    UlsFrequency,
    UlsLicense,
    UlsLocation,
)
from .parser import PARSER_VERSION, ParsedFccArchive

IMPORT_BATCH_SIZE = 5_000


def _chunks(records, size=None):
    size = size or IMPORT_BATCH_SIZE
    iterator = iter(records)
    while chunk := tuple(islice(iterator, size)):
        yield chunk


def _bulk_create(model, records, factory, progress=None):
    total = len(records)
    # Keep UUIDv4 semantics while walking the retained UUID index in ascending order.
    # Allocate identifiers for only this collection; related payloads remain disk-backed.
    identifiers = sorted((uuid.uuid4() for _ in range(total)), reverse=True)
    completed = 0
    if progress:
        progress(model._meta.model_name, completed, total)
    for records_chunk in _chunks(records):
        model.objects.bulk_create(
            [factory(record, identifiers.pop()) for record in records_chunk],
            batch_size=IMPORT_BATCH_SIZE,
        )
        completed += len(records_chunk)
        if progress and (completed % 100_000 == 0 or completed == total):
            progress(model._meta.model_name, completed, total)


@transaction.atomic
def apply_complete_archive(
    *, parsed: ParsedFccArchive, source_url: str, retrieved_at, actor, progress=None
):
    existing = FccImportBatch.objects.filter(
        dataset=parsed.dataset, content_sha256=parsed.content_sha256
    ).first()
    if existing:
        return existing, False

    FccImportBatch.objects.select_for_update().filter(
        dataset=parsed.dataset, is_current=True
    ).update(is_current=False)
    batch = FccImportBatch.objects.create(
        dataset=parsed.dataset,
        archive_kind=FccImportBatch.ArchiveKind.COMPLETE,
        archive_name=parsed.archive_name,
        source_url=source_url,
        content_sha256=parsed.content_sha256,
        parser_version=PARSER_VERSION,
        retrieved_at=retrieved_at,
        record_counts=parsed.record_counts,
        imported_by=actor,
    )
    if parsed.structures:
        _bulk_create(
            AntennaStructure,
            parsed.structures,
            lambda record, identifier: AntennaStructure(id=identifier, batch=batch, **record),
            progress,
        )
    if parsed.licenses:
        _bulk_create(
            UlsLicense,
            parsed.licenses,
            lambda record, identifier: UlsLicense(id=identifier, batch=batch, **record),
            progress,
        )
        license_ids_by_source_id = dict(
            UlsLicense.objects.filter(batch=batch)
            .values_list("unique_system_identifier", "id")
            .iterator(chunk_size=IMPORT_BATCH_SIZE)
        )

        def related(model, records):
            def make_object(record, identifier):
                values = dict(record)
                source_id = values.pop("license_source_id")
                return model(
                    id=identifier, license_id=license_ids_by_source_id[source_id], **values
                )

            _bulk_create(model, records, make_object, progress)

        related(UlsLocation, parsed.locations)
        related(UlsFrequency, parsed.frequencies)
        related(UlsEmission, parsed.emissions)

    record_event(
        actor=actor,
        action="fcc_reference.complete_imported",
        target=batch,
        details={
            "dataset": parsed.dataset,
            "archive_name": parsed.archive_name,
            "content_sha256": parsed.content_sha256,
            "parser_version": PARSER_VERSION,
            "record_counts": parsed.record_counts,
        },
    )
    return batch, True
