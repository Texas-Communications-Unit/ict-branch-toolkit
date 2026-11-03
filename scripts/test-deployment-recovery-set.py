"""Synthetic recovery-set tests; Docker and all production operations are mocked."""

import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "recovery_set", Path(__file__).with_name("deployment-recovery-set.py")
)
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.environment = self.root / "private.env"
        self.environment.write_text("SYNTHETIC_SECRET=fixture-only\n")
        self.calls = []
        self.failure = None
        self.services = b"db\nbackend\nfrontend\n"

    def docker(self, command, **kwargs):
        arguments = command[command.index("-f") + 2 :]
        self.calls.append(arguments)
        text = " ".join(arguments)
        stage = ""
        result = b""
        if arguments[0] == "ps":
            result = self.services
        elif "psql" in text:
            result = b"1024\n"
        elif "du -sk" in text:
            result = b"0\n"
        elif arguments[0] == "stop":
            stage = "stop"
        elif "pg_dump" in text:
            stage = "dump"
            kwargs["stdout"].write(b"PGDMP synthetic database")
        elif "pg_restore" in text:
            stage = "catalog"
        elif "tar -czf" in text:
            stage = "attachments"
            with tarfile.open(fileobj=kwargs["stdout"], mode="w:gz") as archive:
                item = tarfile.TarInfo("synthetic.txt")
                item.size = 4
                archive.addfile(item, io.BytesIO(b"test"))
        elif "tar -tzf" in text:
            stage = "attachment_validation"
            with tarfile.open(fileobj=kwargs["stdin"], mode="r:gz") as archive:
                self.assertEqual(archive.extractfile("synthetic.txt").read(), b"test")
        elif arguments[0] == "up":
            stage = "resume"
        else:
            self.fail(f"Unexpected Docker operation: {arguments}")
        if self.failure == stage:
            raise subprocess.CalledProcessError(1, command)
        return subprocess.CompletedProcess(command, 0, result)

    def create(self):
        with patch.object(recovery.subprocess, "run", self.docker):
            return recovery.create_recovery_set(
                self.environment,
                self.root / "compose.yaml",
                self.root / "backups",
                "a" * 40,
                "b" * 40,
            )

    def test_complete_matched_set_and_private_permissions(self):
        dump = self.create()
        manifest = json.loads(Path(str(dump) + ".recovery.json").read_text())
        self.assertEqual(manifest["source_commit"], "a" * 40)
        self.assertEqual(manifest["target_commit"], "b" * 40)
        for name in manifest["files"]:
            path = dump.parent / name
            digest = Path(str(path) + ".sha256").read_text().split()[0]
            self.assertEqual(digest, hashlib.sha256(path.read_bytes()).hexdigest())
            if os.name == "posix":
                self.assertEqual(path.stat().st_mode & 0o077, 0)
        self.assertEqual(
            Path(str(dump) + ".deployment.env").read_bytes(),
            self.environment.read_bytes(),
        )
        operations = [c[0] for c in self.calls]
        self.assertLess(operations.index("stop"), operations.index("up"))
        self.assertEqual(
            self.calls[-1],
            [
                "up",
                "--no-deps",
                "--no-recreate",
                "--no-build",
                "--wait",
                "backend",
                "frontend",
            ],
        )
        self.assertNotIn("fixture-only", json.dumps(manifest))

    def test_failures_resume_original_services_and_do_not_mark_complete(self):
        for stage in (
            "stop",
            "dump",
            "catalog",
            "attachments",
            "attachment_validation",
        ):
            with self.subTest(stage=stage):
                self.failure = stage
                self.calls = []
                with self.assertRaises(subprocess.CalledProcessError):
                    self.create()
                self.assertEqual(
                    self.calls[-1],
                    [
                        "up",
                        "--no-deps",
                        "--no-recreate",
                        "--no-build",
                        "--wait",
                        "backend",
                        "frontend",
                    ],
                )
                self.assertEqual(
                    list((self.root / "backups").glob("*.recovery.json")), []
                )

    def test_inactive_stack_is_not_started_or_stopped(self):
        self.services = b"db\nbackend\n"
        with self.assertRaises(RuntimeError):
            self.create()
        self.assertEqual([c[0] for c in self.calls], ["ps"])

    def test_preserves_original_protected_configuration_before_candidate_overlays(self):
        original = self.root / "original.env"
        original.write_text("FIXTURE_SOURCE=original\n")
        with patch.object(recovery.subprocess, "run", self.docker):
            dump = recovery.create_recovery_set(
                self.environment,
                self.root / "compose.yaml",
                self.root / "backups",
                "a" * 40,
                "b" * 40,
                original,
            )
        self.assertEqual(
            Path(str(dump) + ".deployment.env").read_bytes(), original.read_bytes()
        )

    def test_insufficient_space_does_not_pause_application(self):
        with patch.object(
            recovery.shutil, "disk_usage", return_value=type("Disk", (), {"free": 0})()
        ):
            with self.assertRaises(RuntimeError):
                self.create()
        self.assertNotIn("stop", [c[0] for c in self.calls])

    def test_resume_failure_is_not_reported_as_success(self):
        self.failure = "resume"
        with self.assertRaises(subprocess.CalledProcessError):
            self.create()

    def test_repeated_clock_value_does_not_overwrite_a_previous_set(self):
        with patch.object(recovery, "datetime") as clock:
            clock.now.return_value.strftime.return_value = "20261102T000000000000Z"
            first = self.create()
            second = self.create()
        self.assertNotEqual(first, second)
        self.assertTrue(first.is_file())
        self.assertTrue(second.is_file())


class RetentionTests(unittest.TestCase):
    def test_expired_complete_set_is_removed_but_corrupt_companions_are_retained(self):
        script = Path(__file__).with_name("deploy-shared-test.sh").read_text()
        code = script.split(
            'python3 - "$backup_dir" "$backup_retention_count" <<\'PY\'\n', 1
        )[1]
        code = code.split("\nPY\n", 1)[0]
        for corrupt in (False, True):
            with (
                self.subTest(corrupt=corrupt),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                dumps = []
                for index in range(2):
                    dump = root / f"postgresql-{index}.dump"
                    members = [
                        dump,
                        Path(str(dump) + ".attachments.tar.gz"),
                        Path(str(dump) + ".deployment.env"),
                    ]
                    for member in members:
                        member.write_bytes(b"synthetic fixture")
                        recovery.checksum(member)
                    Path(str(dump) + ".recovery.json").write_text(
                        json.dumps(
                            {
                                "format": "ict-toolkit-recovery-set-v1",
                                "files": [p.name for p in members],
                            }
                        )
                    )
                    os.utime(dump, (index + 1, index + 1))
                    dumps.append(dump)
                if corrupt:
                    Path(str(dumps[0]) + ".attachments.tar.gz.sha256").write_text("")
                result = subprocess.run(
                    [sys.executable, "-c", code, str(root), "2"],
                    check=True,
                    capture_output=True,
                )
                self.assertTrue(dumps[1].is_file())
                self.assertEqual(dumps[0].exists(), corrupt)
                self.assertEqual(
                    Path(str(dumps[0]) + ".deployment.env").exists(), corrupt
                )
                self.assertNotIn(b"synthetic fixture", result.stdout)


if __name__ == "__main__":
    unittest.main()
