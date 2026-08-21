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
        AntennaStructure.objects.bulk_create(
            [AntennaStructure(batch=batch, **record) for record in parsed.structures]
        )
    if parsed.licenses:
        licenses = [UlsLicense(batch=batch, **record) for record in parsed.licenses]
        UlsLicense.objects.bulk_create(licenses)
        license_by_source_id = {license.unique_system_identifier: license for license in licenses}

        def related(model, records):
            objects = []
            for record in records:
                values = dict(record)
                source_id = values.pop("license_source_id")
                objects.append(model(license=license_by_source_id[source_id], **values))
            model.objects.bulk_create(objects)

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
