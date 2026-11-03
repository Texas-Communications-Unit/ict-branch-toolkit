#!/usr/bin/env python3
"""Exercise a real recovery set using an isolated, synthetic Docker project."""

import importlib.util
import json
import subprocess
import tarfile
import tempfile
import uuid
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "recovery_set", Path(__file__).with_name("deployment-recovery-set.py")
)
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)

with tempfile.TemporaryDirectory(prefix="ict-recovery-check-") as directory:
    root = Path(directory)
    project = "ict-recovery-check-" + uuid.uuid4().hex[:12]
    image = "postgis/postgis:17-3.5-alpine"
    sleeping = {
        "image": image,
        "entrypoint": ["sh"],
        "command": ["-c", "trap 'exit 0' TERM INT; while :; do sleep 1; done"],
    }
    configuration = {
        "name": project,
        "services": {
            "db": {
                "image": image,
                "environment": {
                    "POSTGRES_USER": "synthetic",
                    "POSTGRES_DB": "synthetic",
                    "POSTGRES_PASSWORD": "synthetic-fixture-only",
                },
                "healthcheck": {
                    "test": ["CMD", "pg_isready", "-h", "127.0.0.1", "-U", "synthetic"],
                    "interval": "2s",
                    "timeout": "2s",
                    "retries": 30,
                },
            },
            "backend": dict(sleeping, volumes=["attachments:/app/media"]),
            "frontend": sleeping,
        },
        "volumes": {"attachments": {}},
    }
    compose_file = root / "compose.json"
    compose_file.write_text(json.dumps(configuration))
    env_file = root / "synthetic.env"
    env_file.write_text("FIXTURE_ONLY=1\n")
    compose = ["docker", "compose", "--env-file", str(env_file), "-f", str(compose_file)]

    def run(arguments, **kwargs):
        return subprocess.run(compose + arguments, check=True, **kwargs)

    try:
        run(["up", "--detach", "--wait"])
        run(
            [
                "exec",
                "-T",
                "db",
                "psql",
                "-U",
                "synthetic",
                "-d",
                "synthetic",
                "-c",
                "CREATE TABLE marker(value text); INSERT INTO marker VALUES ('fixture');",
            ]
        )
        run(["exec", "-T", "backend", "sh", "-c", "printf fixture > /app/media/synthetic.txt"])
        dump = recovery.create_recovery_set(
            env_file, compose_file, root / "backups", "a" * 40, "b" * 40
        )
        run(["exec", "-T", "db", "createdb", "-U", "synthetic", "restored"])
        with dump.open("rb") as stream:
            run(
                [
                    "exec",
                    "-T",
                    "db",
                    "pg_restore",
                    "--exit-on-error",
                    "--no-owner",
                    "--no-privileges",
                    "-U",
                    "synthetic",
                    "-d",
                    "restored",
                ],
                stdin=stream,
            )
        result = run(
            [
                "exec",
                "-T",
                "db",
                "psql",
                "-U",
                "synthetic",
                "-d",
                "restored",
                "-Atc",
                "SELECT value FROM marker;",
            ],
            stdout=subprocess.PIPE,
        )
        assert result.stdout.strip() == b"fixture"
        with tarfile.open(str(dump) + ".attachments.tar.gz") as archive:
            assert archive.extractfile("./synthetic.txt").read() == b"fixture"
        result = run(["ps", "--status", "running", "--services"], stdout=subprocess.PIPE)
        assert set(result.stdout.decode().splitlines()) == {"db", "backend", "frontend"}
        assert Path(str(dump) + ".recovery.json").is_file()
        print("Isolated Docker database/attachment recovery and service resumption: PASS")
    finally:
        # Only the randomly named synthetic project defined above is removed.
        assert project.startswith("ict-recovery-check-")
        run(["down", "--volumes", "--remove-orphans"])
