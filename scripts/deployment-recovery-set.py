#!/usr/bin/env python3
"""Create a consistent, private recovery set before changing deployed code."""

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path


def checksum(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    path.with_name(path.name + ".sha256").write_text(
        f"{digest.hexdigest()}  {path.name}\n"
    )


def create_recovery_set(
    env_file,
    compose_file,
    backup_dir,
    source_commit,
    target_commit,
    protected_env_file=None,
):
    os.umask(0o077)
    compose = [
        "docker",
        "compose",
        "--env-file",
        str(env_file),
        "-f",
        str(compose_file),
    ]

    def run(arguments, **kwargs):
        # Do not print Compose configuration or subprocess errors containing secrets.
        return subprocess.run(compose + arguments, check=True, **kwargs)

    def output(arguments):
        return run(arguments, stdout=subprocess.PIPE).stdout.decode().strip()

    running = set(output(["ps", "--status", "running", "--services"]).splitlines())
    if not {"db", "backend", "frontend"}.issubset(running):
        raise RuntimeError(
            "All production services must be running before an upgrade backup"
        )
    db_size = int(
        output(
            [
                "exec",
                "-T",
                "db",
                "sh",
                "-c",
                'export PGPASSWORD="$POSTGRES_PASSWORD"; '
                'exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc '
                '"SELECT pg_database_size(current_database());"',
            ]
        )
    )
    media_kib = int(
        output(
            [
                "run",
                "--rm",
                "--no-deps",
                "--entrypoint",
                "sh",
                "backend",
                "-c",
                "du -sk /app/media | cut -f1",
            ]
        )
    )
    backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    if shutil.disk_usage(backup_dir).free < db_size + media_kib * 1024 + 1024**3:
        raise RuntimeError(
            "Insufficient free space for the database and attachments recovery set"
        )
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    prefix = (
        backup_dir
        / f"postgresql-{timestamp}-pre-{target_commit[:12]}-{uuid.uuid4().hex[:8]}"
    )
    dump = Path(str(prefix) + ".dump")
    attachments = Path(str(dump) + ".attachments.tar.gz")
    environment = Path(str(dump) + ".deployment.env")
    manifest = Path(str(dump) + ".recovery.json")
    paused = False
    try:
        # Keep the pause within the backup phase; builds run after service resumes.
        paused = True  # Also recover from a partially successful stop command.
        run(["stop", "--timeout", "120", "frontend", "backend"], stdout=sys.stderr)
        with dump.open("xb") as stream:
            run(
                [
                    "exec",
                    "-T",
                    "db",
                    "sh",
                    "-c",
                    'export PGPASSWORD="$POSTGRES_PASSWORD"; exec pg_dump '
                    '-U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --no-owner --no-privileges',
                ],
                stdout=stream,
            )
        with dump.open("rb") as stream:
            run(
                ["exec", "-T", "db", "pg_restore", "--list"],
                stdin=stream,
                stdout=subprocess.DEVNULL,
            )
        with attachments.open("xb") as stream:
            run(
                [
                    "run",
                    "--rm",
                    "--no-deps",
                    "--entrypoint",
                    "sh",
                    "backend",
                    "-c",
                    "exec tar -czf - -C /app/media .",
                ],
                stdout=stream,
            )
        with attachments.open("rb") as stream:
            run(
                [
                    "run",
                    "--rm",
                    "--no-deps",
                    "-T",
                    "--entrypoint",
                    "sh",
                    "backend",
                    "-c",
                    "exec tar -tzf - >/dev/null",
                ],
                stdin=stream,
                stdout=subprocess.DEVNULL,
            )
        with (
            (protected_env_file or env_file).open("rb") as source,
            environment.open("xb") as destination,
        ):
            shutil.copyfileobj(source, destination)
        for path in (dump, attachments, environment):
            checksum(path)
        # Only this final marker declares the matched set complete.
        with manifest.open("x") as stream:
            json.dump(
                {
                    "format": "ict-toolkit-recovery-set-v1",
                    "source_commit": source_commit,
                    "target_commit": target_commit,
                    "created_utc": timestamp,
                    "files": [p.name for p in (dump, attachments, environment)],
                },
                stream,
            )
            stream.write("\n")
    finally:
        if paused:
            run(
                [
                    "up",
                    "--no-deps",
                    "--no-recreate",
                    "--no-build",
                    "--wait",
                    "backend",
                    "frontend",
                ],
                stdout=sys.stderr,
            )
    return dump


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "env-file",
        "compose-file",
        "backup-dir",
        "source-commit",
        "target-commit",
    ):
        parser.add_argument("--" + name, required=True)
    parser.add_argument(
        "--protected-env-file", help="Original protected configuration before overlays"
    )
    args = parser.parse_args()
    for value in (args.source_commit, args.target_commit):
        if not re.fullmatch(r"[0-9a-f]{40}", value):
            parser.error("Commit identities must be exact 40-character SHA values")

    def interrupted(signum, frame):
        raise InterruptedError("Recovery-set creation interrupted")

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        dump = create_recovery_set(
            Path(args.env_file).resolve(),
            Path(args.compose_file).resolve(),
            Path(args.backup_dir).resolve(),
            args.source_commit,
            args.target_commit,
            Path(args.protected_env_file).resolve()
            if args.protected_env_file
            else None,
        )
    except Exception as error:
        print(
            f"Recovery-set creation failed ({type(error).__name__}); code was not promoted. "
            "Check application service health and retain incomplete artifacts for review.",
            file=sys.stderr,
        )
        return 1
    print(dump)
    return 0


if __name__ == "__main__":
    sys.exit(main())
