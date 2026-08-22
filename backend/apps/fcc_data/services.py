from __future__ import annotations

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
    for start in range(0, len(records), size):
        yield records[start : start + size]


def _bulk_create(model, records, factory):
    for records_chunk in _chunks(records):
        model.objects.bulk_create(
            [factory(record) for record in records_chunk],
            batch_size=IMPORT_BATCH_SIZE,
        )


@transaction.atomic
def apply_complete_archive(*, parsed: ParsedFccArchive, source_url: str, retrieved_at, actor):
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
            lambda record: AntennaStructure(batch=batch, **record),
        )
    if parsed.licenses:
        _bulk_create(
            UlsLicense,
            parsed.licenses,
            lambda record: UlsLicense(batch=batch, **record),
        )
        license_ids_by_source_id = dict(
            UlsLicense.objects.filter(batch=batch)
            .values_list("unique_system_identifier", "id")
            .iterator(chunk_size=IMPORT_BATCH_SIZE)
        )

        def related(model, records):
            def make_object(record):
                values = dict(record)
                source_id = values.pop("license_source_id")
                return model(license_id=license_ids_by_source_id[source_id], **values)

            _bulk_create(model, records, make_object)

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
