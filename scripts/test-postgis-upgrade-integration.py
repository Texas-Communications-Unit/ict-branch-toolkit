#!/usr/bin/env python3
"""Exercise existing PG17/PostGIS3.5 data, a 3.6 upgrade, and dump-based rollback."""

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path


def docker(*args, **kwargs):
    try:
        return subprocess.run(["docker", *args], check=True, **kwargs)
    except subprocess.CalledProcessError as error:
        # This fixture contains synthetic data/credentials only. Preserve the
        # captured cause so a failed upgrade is diagnosable in CI evidence.
        if error.stderr:
            detail = error.stderr
            print(
                detail.decode() if isinstance(detail, bytes) else detail,
                file=sys.stderr,
            )
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-image", required=True)
    parser.add_argument("--backend-image", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    prefix = "ict-postgis-upgrade-" + uuid.uuid4().hex[:12]
    network = prefix + "-net"
    containers, volumes = [], []
    # This baseline intentionally stays 3.5: it represents the previous release.
    baseline = "postgis/postgis:17-3.5-alpine"
    password = "synthetic-upgrade-fixture-only"
    user, database = "synthetic", "synthetic"

    def sql(container, query):
        result = docker(
            "exec",
            "-i",
            container,
            "psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            user,
            "-d",
            database,
            "-At",
            input=query,
            text=True,
            capture_output=True,
        )
        return result.stdout.strip()

    def start(suffix, image, volume):
        name = prefix + "-" + suffix
        containers.append(name)
        docker(
            "run",
            "--detach",
            "--name",
            name,
            "--network",
            network,
            "--env",
            "POSTGRES_USER=" + user,
            "--env",
            "POSTGRES_DB=" + database,
            "--env",
            "POSTGRES_PASSWORD=" + password,
            "--volume",
            volume + ":/var/lib/postgresql/data",
            image,
            capture_output=True,
        )
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            # Require the network listener, not initdb's temporary local server.
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    name,
                    "pg_isready",
                    "-h",
                    "127.0.0.1",
                    "-U",
                    user,
                    "-d",
                    database,
                ],
                capture_output=True,
                check=False,
            )
            if result.returncode == 0:
                assert int(sql(name, "SHOW server_version_num")) // 10000 == 17
                return name
            time.sleep(2)
        raise RuntimeError("Synthetic database startup timed out")

    def new_volume(suffix):
        name = prefix + "-" + suffix
        docker("volume", "create", name, capture_output=True)
        volumes.append(name)
        return name

    def versions(container):
        return json.loads(
            sql(
                container,
                """
            SELECT json_object_agg(extname, extversion) FROM pg_extension
            WHERE extname IN ('postgis','postgis_topology','postgis_tiger_geocoder');
        """,
            )
        )

    def marker(container):
        return json.loads(
            sql(
                container,
                """
            SELECT json_build_object(
              'id', id, 'description', description,
              'geometry', encode(ST_AsEWKB(geom), 'hex'),
              'geography', encode(ST_AsEWKB(location::geometry), 'hex'),
              'index', EXISTS (SELECT 1 FROM pg_indexes WHERE indexname='spatial_fixture_gist'),
              'custom_srid', EXISTS(SELECT 1 FROM spatial_ref_sys WHERE srid=910001)
            ) FROM spatial_fixture;
        """,
            )
        )

    def upgrade(container):
        result = docker(
            "run",
            "--rm",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--network",
            network,
            "--env",
            f"DATABASE_URL=postgis://{user}:{password}@{container}:5432/{database}",
            "--env",
            "DJANGO_ENABLE_GIS=true",
            "--env",
            "DJANGO_SECRET_KEY=synthetic-upgrade-secret-only",
            args.backend_image,
            "python",
            "manage.py",
            "upgrade_postgis",
            text=True,
            capture_output=True,
        )
        return result.stdout

    evidence = {"classification": "synthetic-only", "postgresql_major": 17}
    try:
        docker("pull", baseline, capture_output=True)
        docker("network", "create", "--internal", network, capture_output=True)
        volume = new_volume("existing-data")
        old = start("old", baseline, volume)
        assert all(version.startswith("3.5.") for version in versions(old).values())
        sql(
            old,
            """
            CREATE TABLE spatial_fixture (
              id integer PRIMARY KEY, description text,
              geom geometry(Point,4326), location geography(Point,4326)
            );
            INSERT INTO spatial_fixture VALUES (
              1, 'synthetic-preservation-marker',
              ST_SetSRID(ST_MakePoint(-97.13,33.21),4326),
              ST_SetSRID(ST_MakePoint(-97.13,33.21),4326)::geography
            );
            CREATE INDEX spatial_fixture_gist ON spatial_fixture USING gist(geom);
            INSERT INTO spatial_ref_sys(srid,auth_name,auth_srid,srtext,proj4text)
              SELECT 910001,'SYNTHETIC',910001,srtext,proj4text FROM spatial_ref_sys WHERE srid=4326;
        """,
        )
        expected = marker(old)
        evidence["before_extensions"] = versions(old)
        with tempfile.TemporaryDirectory(prefix="ict-postgis-dump-") as temporary:
            archive = Path(temporary) / "before.dump"
            with archive.open("wb") as output:
                docker(
                    "exec",
                    old,
                    "pg_dump",
                    "-U",
                    user,
                    "-d",
                    database,
                    "--format=custom",
                    "--no-owner",
                    "--no-privileges",
                    stdout=output,
                )
            archive.chmod(0o600)
            checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
            evidence["pre_upgrade_dump_sha256"] = checksum
            docker("stop", old, capture_output=True)
            docker("rm", old, capture_output=True)
            containers.remove(old)

            current = start("upgraded", args.database_image, volume)
            # Replacing the image alone must not be mistaken for an SQL upgrade.
            assert versions(current)["postgis"].startswith("3.5.")
            assert "upgraded and verified" in upgrade(current)
            assert marker(current) == expected
            assert all(
                version.startswith("3.6.") for version in versions(current).values()
            )
            assert "already current" in upgrade(current)
            evidence["after_extensions"] = versions(current)
            evidence["existing_volume_preserved"] = True
            evidence["upgrade_idempotent"] = True

            for suffix, image, expected_minor in (
                ("restored-new", args.database_image, "3.6."),
                ("rollback-old", baseline, "3.5."),
            ):
                restored = start(suffix, image, new_volume(suffix))
                assert hashlib.sha256(archive.read_bytes()).hexdigest() == checksum
                with archive.open("rb") as stream:
                    docker(
                        "exec",
                        "-i",
                        restored,
                        "pg_restore",
                        "--exit-on-error",
                        "--clean",
                        "--if-exists",
                        "--no-owner",
                        "--no-privileges",
                        "-U",
                        user,
                        "-d",
                        database,
                        stdin=stream,
                        capture_output=True,
                    )
                assert marker(restored) == expected
                assert all(
                    version.startswith(expected_minor)
                    for version in versions(restored).values()
                )
                evidence[suffix + "_verified"] = True
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(json.dumps(evidence, indent=2) + "\n")
        print(
            "Existing-volume upgrade, spatial data preservation, 3.6 restore and 3.5 rollback passed."
        )
    finally:
        # Only exact resource names generated by this invocation may be removed.
        for container in containers:
            assert container.startswith(prefix + "-")
            subprocess.run(
                ["docker", "rm", "--force", container], capture_output=True, check=False
            )
        for volume in volumes:
            assert volume.startswith(prefix + "-")
            subprocess.run(
                ["docker", "volume", "rm", volume], capture_output=True, check=False
            )
        subprocess.run(
            ["docker", "network", "rm", network], capture_output=True, check=False
        )


if __name__ == "__main__":
    main()
