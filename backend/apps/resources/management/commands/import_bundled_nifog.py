import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.resources.models import ResourceRelease
from apps.resources.serializers import ChannelImportSerializer
from apps.resources.services import apply_import, preview_import, reference_is_approved


class Command(BaseCommand):
    help = "Validate or apply the bundled, checksum-pinned NIFOG 2.02 release."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Persist the release after validation and approval checks.",
        )
        parser.add_argument(
            "--username",
            help="Existing administrator recorded as the import actor when using --apply.",
        )
        parser.add_argument(
            "--if-approved",
            action="store_true",
            help="Exit successfully without importing when the exact release is not approved.",
        )

    def handle(self, *args, **options):
        payload_path = Path(settings.BASE_DIR) / "data" / "reference" / "nifog-2.02.json"
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        payload["dry_run"] = not options["apply"]

        serializer = ChannelImportSerializer(data=payload)
        if not serializer.is_valid():
            raise CommandError(f"Bundled NIFOG data is invalid: {serializer.errors}")

        source = serializer.validated_data["source"]
        release = serializer.validated_data["release"]
        existing = ResourceRelease.objects.filter(
            source__slug=source["slug"], version=release["version"]
        ).first()
        if existing:
            self.stdout.write(
                self.style.SUCCESS(
                    f"NIFOG {existing.version} is already imported as release {existing.id}."
                )
            )
            return

        if not options["apply"]:
            preview = preview_import(serializer.validated_data)
            counts = preview["would_create"]
            self.stdout.write(
                self.style.SUCCESS(
                    "NIFOG 2.02 is valid: "
                    f"{counts['conventional_channels']} conventional channels and "
                    f"{counts['trunked_talkgroups']} trunked talkgroups."
                )
            )
            if preview["approval_required"]:
                self.stdout.write("The exact release still requires configured approval.")
            return

        if not reference_is_approved(source, release):
            if options["if_approved"]:
                self.stdout.write("NIFOG 2.02 is not configured as approved; import skipped.")
                return
            raise CommandError("The exact bundled NIFOG 2.02 release is not approved.")

        username = options["username"]
        if not username:
            raise CommandError("--username is required with --apply.")
        try:
            actor = get_user_model().objects.get(username=username)
        except get_user_model().DoesNotExist as error:
            raise CommandError(f"Import actor {username!r} does not exist.") from error

        record = apply_import(
            validated_data=serializer.validated_data,
            raw_payload=payload,
            actor=actor,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Imported NIFOG 2.02 as release {record.release_id}: "
                f"{record.conventional_count} conventional channels and "
                f"{record.talkgroup_count} trunked talkgroups."
            )
        )
