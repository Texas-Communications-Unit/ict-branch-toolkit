"""Bounded public-reference metadata; never scan reference rows for a status page."""

import re

from django.utils import timezone

from .models import FccImportBatch
from .parser import EXPECTED_ARCHIVES

COUNT_KEYS = {
    "asr": ("antenna_structures",),
    "uls_private": ("licenses", "locations", "frequencies", "emissions"),
    "uls_commercial": ("licenses", "locations", "frequencies", "emissions"),
}


def dataset_status():
    now = timezone.now()
    datasets = []
    for dataset, label in FccImportBatch.Dataset.choices:
        # Limit conflicting metadata as well as the ordinary single-current case.
        batches = list(
            FccImportBatch.objects.filter(dataset=dataset, is_current=True)
            .order_by("-imported_at", "-id")
            .values(
                "id",
                "archive_name",
                "source_url",
                "content_sha256",
                "parser_version",
                "retrieved_at",
                "imported_at",
                "record_counts",
            )[:2]
        )
        item = {
            "dataset": dataset,
            "label": label,
            "status": "not_imported" if not batches else "ambiguous",
            "retrieved_at": None,
            "imported_at": None,
            "retrieved_age_days": None,
            "timestamp_warning": False,
            "last_checked_at": None,
            "record_counts": {key: None for key in COUNT_KEYS[dataset]},
            "archive_name": None,
            "source_url": None,
            "content_sha256": None,
            "parser_version": None,
        }
        if len(batches) == 1:
            batch = batches[0]
            expected_archive = EXPECTED_ARCHIVES[dataset]
            expected_url = f"https://data.fcc.gov/download/pub/uls/complete/{expected_archive}"
            raw_counts = batch["record_counts"]
            if not isinstance(raw_counts, dict):
                raw_counts = {}
            counts = {}
            for key in COUNT_KEYS[dataset]:
                value = raw_counts.get(key)
                counts[key] = value if type(value) is int and 0 <= value <= 2**53 - 1 else None
            age = now - batch["retrieved_at"]
            future = age.total_seconds() < 0 or batch["imported_at"] > now
            digest = batch["content_sha256"]
            parser = batch["parser_version"]
            item.update(
                status="available",
                retrieved_at=batch["retrieved_at"],
                imported_at=batch["imported_at"],
                retrieved_age_days=None if future else age.days,
                timestamp_warning=future,
                record_counts=counts,
                archive_name=expected_archive
                if batch["archive_name"] == expected_archive
                else None,
                source_url=expected_url if batch["source_url"] == expected_url else None,
                content_sha256=digest if re.fullmatch(r"[0-9a-f]{64}", digest) else None,
                parser_version=parser if re.fullmatch(r"[A-Za-z0-9._-]{1,40}", parser) else None,
            )
        datasets.append(item)
    return {"generated_at": now, "datasets": datasets}
