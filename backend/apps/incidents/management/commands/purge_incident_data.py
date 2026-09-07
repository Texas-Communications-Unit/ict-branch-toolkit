from __future__ import annotations

import re

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import ForeignKey, OneToOneField, ProtectedError

from apps.extensions.models import ExtensionInstallation
from apps.incidents.models import Incident
from apps.resources.models import (
    ConventionalChannel,
    ResourceImport,
    ResourceRelease,
    ResourceSource,
    TrunkedTalkgroup,
)

CONFIRMATION = "DELETE-ALL-INCIDENT-DATA"


def app_counts(app_label: str) -> dict[str, int]:
    return {
        model._meta.label: model._base_manager.count()
        for model in apps.get_app_config(app_label).get_models()
    }


def incident_root_models():
    roots = []
    for model in apps.get_models():
        if model is Incident:
            continue
        for field in model._meta.fields:
            if (
                isinstance(field, (ForeignKey, OneToOneField))
                and field.remote_field.model is Incident
            ):
                roots.append((model, field.name))
                break
    return roots


class Command(BaseCommand):
    help = "Permanently remove all incident-owned data while proving FCC data is unchanged."

    def add_arguments(self, parser):
        parser.add_argument("--confirm", required=True)
        parser.add_argument("--verified-backup-sha256", required=True)

    def handle(self, *args, **options):
        if options["confirm"] != CONFIRMATION:
            raise CommandError(f"Pass --confirm {CONFIRMATION} to authorize this reset.")
        backup_sha256 = options["verified_backup_sha256"].lower()
        if not re.fullmatch(r"[0-9a-f]{64}", backup_sha256):
            raise CommandError("Pass the verified pre-reset database backup SHA-256 digest.")

        incident_count = Incident._base_manager.count()
        roots = incident_root_models()
        preview = {
            model._meta.label: model._base_manager.filter(
                **{f"{field}_id__in": Incident.objects.values("id")}
            ).count()
            for model, field in roots
        }
        self.stdout.write(f"Incidents selected: {incident_count}")
        self.stdout.write(f"Verified backup SHA-256: {backup_sha256}")
        for label, count in sorted(preview.items()):
            self.stdout.write(f"  {label}: {count}")

        fcc_before = app_counts("fcc_data")
        with transaction.atomic():
            pending = list(roots)
            while pending:
                deferred = []
                progress = False
                for model, field in pending:
                    queryset = model._base_manager.filter(
                        **{f"{field}_id__in": Incident.objects.values("id")}
                    )
                    try:
                        queryset.delete()
                    except ProtectedError:
                        deferred.append((model, field))
                    else:
                        progress = True
                if deferred and not progress:
                    labels = ", ".join(model._meta.label for model, _field in deferred)
                    raise CommandError(f"Protected incident relationships remain: {labels}")
                pending = deferred
            Incident._base_manager.all().delete()
            synthetic_sources = ResourceSource._base_manager.filter(
                source_type=ResourceSource.Type.SYNTHETIC
            )
            synthetic_releases = ResourceRelease._base_manager.filter(source__in=synthetic_sources)
            ResourceImport._base_manager.filter(release__in=synthetic_releases).delete()
            ConventionalChannel._base_manager.filter(release__in=synthetic_releases).delete()
            TrunkedTalkgroup._base_manager.filter(release__in=synthetic_releases).delete()
            synthetic_releases.delete()
            synthetic_sources.delete()
            ExtensionInstallation._base_manager.filter(
                extension_key__startswith="synthetic-"
            ).delete()
            fcc_after = app_counts("fcc_data")
            if fcc_after != fcc_before:
                raise CommandError("FCC table counts changed; the incident reset was rolled back.")

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {incident_count} incidents and dependent records; FCC data is unchanged."
            )
        )
