"""Upgrade installed spatial SQL objects before the application accepts traffic."""

import re

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

EXTENSIONS = (
    "postgis",
    "postgis_raster",
    "postgis_sfcgal",
    "postgis_topology",
    "postgis_tiger_geocoder",
)
INVENTORY_SQL = """
SELECT installed.extname, installed.extversion, available.default_version
FROM pg_extension AS installed
LEFT JOIN pg_available_extensions AS available ON available.name = installed.extname
WHERE installed.extname = ANY(%s)
ORDER BY installed.extname
"""


class Command(BaseCommand):
    help = (
        "Upgrade installed PostGIS extensions to the approved 3.6 runtime; skip non-GIS databases."
    )

    def handle(self, *args, **options):
        if not settings.ENABLE_GIS or connection.vendor != "postgresql":
            self.stdout.write("PostGIS upgrade skipped for a non-GIS database.")
            return

        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout = '60s'")
            cursor.execute("SET LOCAL statement_timeout = '120s'")
            # Serialize simultaneous backend starts without installing an extension
            # that was not already present in the spatial database.
            cursor.execute("SELECT pg_advisory_xact_lock(528005239636)")
            cursor.execute(INVENTORY_SQL, [list(EXTENSIONS)])
            before = cursor.fetchall()
            if not any(name == "postgis" for name, _, _ in before):
                raise CommandError(
                    "PostGIS is missing; initialize the spatial database before startup."
                )
            for name, installed, available in before:
                if not available or not re.fullmatch(r"3\.6\.\d+", available):
                    raise CommandError(f"{name} target {available!r} is not approved stable 3.6.")
                if not re.fullmatch(r"3\.(5|6)\.\d+", installed):
                    raise CommandError(
                        f"{name} version {installed!r} requires a reviewed upgrade path."
                    )
            if all(installed == available for _, installed, available in before):
                self.stdout.write("Installed PostGIS extensions are already current on 3.6.")
                return

            cursor.execute("SELECT postgis_extensions_upgrade()")
            cursor.fetchone()
            cursor.execute(INVENTORY_SQL, [list(EXTENSIONS)])
            after = cursor.fetchall()
            if {name for name, _, _ in after} != {name for name, _, _ in before}:
                raise CommandError(
                    "Unexpected PostGIS extension inventory change; upgrade rolled back."
                )
            if any(installed != available for _, installed, available in after):
                raise CommandError(
                    "PostGIS SQL/library upgrade is incomplete; upgrade rolled back."
                )
        self.stdout.write("Installed PostGIS extensions upgraded and verified on 3.6.")
