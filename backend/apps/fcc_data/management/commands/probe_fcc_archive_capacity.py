import hashlib
import json
import shutil
import zipfile
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.fcc_data.models import FccImportBatch
from apps.fcc_data.parser import (
    EXPECTED_ARCHIVES,
    MAX_EXPANDED_BYTES,
    MAX_MEMBERS,
    REQUIRED_MEMBERS,
)


class Command(BaseCommand):
    help = "Validate an FCC archive and report capacity evidence without database writes."

    def add_arguments(self, parser):
        parser.add_argument("archive", type=Path)
        parser.add_argument("--dataset", required=True, choices=FccImportBatch.Dataset.values)

    def handle(self, *args, **options):
        archive = options["archive"].resolve()
        dataset = options["dataset"]
        if not archive.is_file():
            raise CommandError(f"Archive does not exist: {archive}")
        if archive.name != EXPECTED_ARCHIVES[dataset]:
            raise CommandError(f"Expected archive name {EXPECTED_ARCHIVES[dataset]} for {dataset}.")

        digest = hashlib.sha256()
        with archive.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        try:
            with zipfile.ZipFile(archive) as zipped:
                members = [item for item in zipped.infolist() if not item.is_dir()]
                names = {Path(item.filename).name for item in members}
                missing = REQUIRED_MEMBERS[dataset] - names
                expanded = sum(item.file_size for item in members)
                if len(members) > MAX_MEMBERS:
                    raise CommandError(
                        f"Archive has {len(members)} members; maximum is {MAX_MEMBERS}."
                    )
                if missing:
                    missing_names = ", ".join(sorted(missing))
                    raise CommandError(f"Archive is missing required members: {missing_names}.")
                if expanded > MAX_EXPANDED_BYTES:
                    raise CommandError("Archive expanded size exceeds the configured safety limit.")
        except zipfile.BadZipFile as exc:
            raise CommandError("Archive is not a valid ZIP file.") from exc

        compressed = archive.stat().st_size
        free_disk = shutil.disk_usage(archive.parent).free
        self.stdout.write(
            json.dumps(
                {
                    "dataset": dataset,
                    "archive": archive.name,
                    "sha256": digest.hexdigest(),
                    "compressed_bytes": compressed,
                    "expanded_bytes": expanded,
                    "expansion_ratio": round(expanded / compressed, 2) if compressed else None,
                    "member_count": len(members),
                    "free_disk_bytes": free_disk,
                    "database_writes": 0,
                    "validated": True,
                },
                sort_keys=True,
            )
        )
