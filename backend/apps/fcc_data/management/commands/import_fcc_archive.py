from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.accounts.policy import LIBRARY_IMPORT, user_has_permission
from apps.fcc_data.models import FccImportBatch
from apps.fcc_data.parser import FccArchiveError, parse_fcc_archive
from apps.fcc_data.services import apply_complete_archive


class Command(BaseCommand):
    help = "Validate or apply a local FCC complete public-access archive."

    def add_arguments(self, parser):
        parser.add_argument("archive", type=Path)
        parser.add_argument(
            "--dataset",
            required=True,
            choices=[choice for choice, _label in FccImportBatch.Dataset.choices],
        )
        parser.add_argument(
            "--source-url",
            required=True,
            help="Exact approved FCC HTTPS URL used to retrieve the archive.",
        )
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--username", help="Administrator recorded as the import actor.")

    def handle(self, *args, **options):
        try:
            parsed = parse_fcc_archive(options["archive"], dataset=options["dataset"])
        except FccArchiveError as error:
            raise CommandError(" ".join(error.messages)) from error

        counts = ", ".join(f"{name}={count}" for name, count in parsed.record_counts.items())
        if not options["apply"]:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Valid {parsed.dataset} archive {parsed.archive_name}: {counts}; "
                    f"sha256={parsed.content_sha256}. No data was written."
                )
            )
            return

        if not options["source_url"].startswith("https://data.fcc.gov/download/pub/uls/complete/"):
            raise CommandError("--source-url must identify the approved FCC complete-file host.")
        username = options["username"]
        if not username:
            raise CommandError("--username is required with --apply.")
        try:
            actor = get_user_model().objects.get(username=username, is_active=True)
        except get_user_model().DoesNotExist as error:
            raise CommandError(
                f"Import actor {username!r} does not exist or is inactive."
            ) from error
        if not user_has_permission(actor, LIBRARY_IMPORT):
            raise CommandError("The import actor does not have library import permission.")

        batch, created = apply_complete_archive(
            parsed=parsed,
            source_url=options["source_url"],
            retrieved_at=timezone.now(),
            actor=actor,
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Imported FCC batch {batch.id}: {counts}."))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Archive is already imported as FCC batch {batch.id}; no data was written."
                )
            )
