#!/usr/bin/env python3
"""Synthetic orchestration and isolated Linux process-guard tests; no server access."""

import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def module(name, filename):
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).with_name(filename)
    )
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


AUTOMATION = module("fcc_server_automation", "fcc-server-automation.py")
CLEANUP = module("fcc_memory_cleanup", "fcc-temporary-memory-cleanup.py")


class AutomationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.config = {
            "app_dir": str(self.root),
            "data_dir": str(self.root),
            "state_dir": str(self.root / "state"),
            "env_file": str(self.root / "private.env"),
            "maintenance_lock": str(self.root / "maintenance.lock"),
            "backend_container": "synthetic-backend",
            "notifications_enabled": False,
        }

    def metadata(self):
        archive = self.root / "r_tower.zip"
        archive.write_bytes(b"synthetic public FCC archive")
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        Path(str(archive) + ".imported.sha256").write_text(digest)
        return {
            "asr": [
                {"content_sha256": digest, "record_counts": {"antenna_structures": 1}}
            ]
        }

    def test_verification_requires_database_marker_and_archive_agreement(self):
        metadata = self.metadata()
        with patch.object(AUTOMATION, "run", return_value=json.dumps(metadata)):
            self.assertEqual(
                AUTOMATION.verify_dataset(self.config, "asr"), metadata["asr"][0]
            )
            (self.root / "r_tower.zip").write_bytes(b"changed archive")
            with self.assertRaisesRegex(AUTOMATION.JobError, "digest_mismatch"):
                AUTOMATION.verify_dataset(self.config, "asr")

    def test_multiple_current_batches_are_not_a_success(self):
        metadata = self.metadata()
        metadata["asr"] *= 2
        with (
            patch.object(AUTOMATION, "run", return_value=json.dumps(metadata)),
            self.assertRaisesRegex(AUTOMATION.JobError, "ambiguous"),
        ):
            AUTOMATION.verify_dataset(self.config, "asr")

    def test_command_error_never_exposes_captured_secret_output(self):
        failed = subprocess.CompletedProcess(
            [], 1, "synthetic-secret", "synthetic-secret"
        )
        with (
            patch.object(AUTOMATION.subprocess, "run", return_value=failed),
            self.assertRaisesRegex(AUTOMATION.JobError, "^command_failed$"),
        ):
            AUTOMATION.run(["synthetic"])

    def test_progress_is_aggregate_and_explicitly_uncommitted(self):
        log = self.root / "progress.log"
        log.write_text(
            "Staged 100000/200000 ulsfrequency records (transaction not committed).\n"
        )
        self.assertEqual(
            AUTOMATION.last_progress(log),
            {
                "collection": "ulsfrequency",
                "completed": 100000,
                "total": 200000,
                "committed": False,
            },
        )

    def test_failure_stops_sequence_and_retains_previous_verification(self):
        saved, called = [], []
        args = SimpleNamespace(
            job_name="weekly", dataset="all", after_external_log=None
        )

        def dataset(config, name, sha, state, job):
            called.append(name)
            if name == "uls_commercial":
                raise AUTOMATION.JobError("synthetic_failure")
            state["verified"][name] = {"verified": True}

        with (
            patch.object(
                AUTOMATION,
                "save_status",
                side_effect=lambda c, n, s: saved.append(copy.deepcopy(s)),
            ),
            patch.object(
                AUTOMATION, "file_lock", return_value=contextlib.nullcontext()
            ),
            patch.object(AUTOMATION, "wait_idle"),
            patch.object(AUTOMATION, "deployed_release", return_value="a" * 40),
            patch.object(AUTOMATION, "run_dataset", side_effect=dataset),
            contextlib.redirect_stdout(io.StringIO()),
            self.assertRaisesRegex(AUTOMATION.JobError, "synthetic_failure"),
        ):
            AUTOMATION.execute(self.config, args)
        self.assertEqual(called, ["asr", "uls_commercial"])
        self.assertEqual(saved[-1]["status"], "failed")
        self.assertTrue(saved[-1]["verified"]["asr"]["verified"])

    def test_failed_external_operation_cannot_start_remaining_import(self):
        log = self.root / "fcc-sync-logs/123-1.log"
        log.parent.mkdir()
        log.write_text("synthetic failure")
        args = SimpleNamespace(
            job_name="bootstrap",
            dataset="uls_private",
            after_external_log="123-1",
            after_dataset="uls_commercial",
        )
        with (
            patch.object(AUTOMATION, "save_status"),
            patch.object(
                AUTOMATION, "file_lock", return_value=contextlib.nullcontext()
            ),
            patch.object(AUTOMATION, "wait_idle"),
            patch.object(AUTOMATION, "deployed_release", return_value="a" * 40),
            patch.object(AUTOMATION, "run_dataset") as importer,
        ):
            with self.assertRaisesRegex(AUTOMATION.JobError, "external_import"):
                AUTOMATION.execute(self.config, args)
            importer.assert_not_called()

    def test_disabled_notifications_do_not_read_mail_settings_or_send(self):
        with patch.object(AUTOMATION, "run") as command:
            self.assertFalse(AUTOMATION.notify(self.config, "synthetic", "synthetic"))
            command.assert_not_called()

    def test_mail_authentication_requires_encryption(self):
        settings = {
            "ICT_EMAIL_ENABLED": "true",
            "DJANGO_EMAIL_USE_TLS": "false",
            "DJANGO_EMAIL_USE_SSL": "false",
            "DJANGO_EMAIL_HOST_USER": "synthetic",
        }
        self.config["notifications_enabled"] = True
        with (
            patch.object(
                AUTOMATION,
                "run",
                return_value=json.dumps(
                    {"services": {"backend": {"environment": settings}}}
                ),
            ),
            self.assertRaisesRegex(AUTOMATION.JobError, "require_encryption"),
        ):
            AUTOMATION.notify(self.config, "synthetic", "synthetic")

    def test_failure_email_uses_existing_mail_transport(self):
        settings = {
            "ICT_EMAIL_ENABLED": "true",
            "DJANGO_EMAIL_USE_TLS": "true",
            "DJANGO_EMAIL_USE_SSL": "false",
            "DJANGO_EMAIL_HOST_USER": "synthetic",
            "DJANGO_EMAIL_HOST_PASSWORD": "synthetic-only",
            "DJANGO_EMAIL_HOST": "smtp.example.invalid",
            "DJANGO_EMAIL_PORT": "587",
            "DJANGO_DEFAULT_FROM_EMAIL": "noreply@example.invalid",
        }
        self.config.update(
            notifications_enabled=True, notification_email="operator@example.invalid"
        )
        smtp = MagicMock()
        with (
            patch.object(
                AUTOMATION,
                "run",
                return_value=json.dumps(
                    {"services": {"backend": {"environment": settings}}}
                ),
            ),
            patch.object(AUTOMATION.smtplib, "SMTP", return_value=smtp),
        ):
            self.assertTrue(
                AUTOMATION.notify(self.config, "Synthetic failure", "No records.")
            )
        smtp.__enter__.return_value.starttls.assert_called_once()
        smtp.__enter__.return_value.send_message.assert_called_once()

    @unittest.skipUnless(os.name == "posix", "POSIX ownership checks")
    def test_cleanup_refuses_unrelated_files_and_outside_paths(self):
        target = self.root / "retain.txt"
        target.write_bytes(b"retain")
        target.chmod(0o600)
        with self.assertRaisesRegex(ValueError, "name_refused"):
            CLEANUP.validate_target(target, self.root)
        named = self.root / "fcc-import-20261104.swap"
        named.write_bytes(b"retain")
        named.chmod(0o600)
        with self.assertRaisesRegex(ValueError, "metadata_refused"):
            CLEANUP.validate_target(named, self.root, expected_uid=os.geteuid())
        with self.assertRaisesRegex(ValueError, "path_refused"):
            CLEANUP.validate_target(named, self.root / "different")
        self.assertEqual(named.read_bytes(), b"retain")
        self.assertEqual(target.read_bytes(), b"retain")


@unittest.skipUnless(
    sys.platform == "linux", "Isolated Linux resource-limit syscall test"
)
class ProcessGuardTests(unittest.TestCase):
    def test_only_verified_import_is_limited_and_pid_reuse_is_refused(self):
        directory = Path("/tmp") / ("ict-fcc-" + uuid.uuid4().hex[:8])
        directory.mkdir(mode=0o700)
        self.addCleanup(lambda: __import__("shutil").rmtree(directory))
        script = directory / "manage.py"
        script.write_text(
            "import pathlib,time\npathlib.Path(__file__).with_name('ready').touch()\ntime.sleep(60)\n"
        )
        child = subprocess.Popen(
            [
                sys.executable,
                str(script),
                "import_fcc_archive",
                str(directory / "l_LMpriv.zip"),
                "--dataset",
                "uls_private",
                "--work-dir",
                str(directory),
            ]
        )
        self.addCleanup(lambda: child.poll() is None and child.kill())
        for _ in range(100):
            if (directory / "ready").exists():
                break
            time.sleep(0.02)

        def probe(request):
            result = subprocess.run(
                [sys.executable, "-c", AUTOMATION.PROCESS_PROGRAM],
                input=json.dumps(request),
                text=True,
                capture_output=True,
                check=True,
                timeout=10,
            )
            return json.loads(result.stdout)

        result = probe({"mode": "limit", "dataset": "uls_private", "memory_mib": 256})
        self.assertNotIn("error", result)
        selected = result["processes"][0]
        self.assertEqual(selected["pid"], child.pid)
        self.assertLessEqual(selected["limit_bytes"], 256 * 1024**2)
        wrong = {**selected, "start": "wrong"}
        self.assertIn(
            "error",
            probe({"mode": "stop", "dataset": "uls_private", "expected": wrong}),
        )
        self.assertIsNone(child.poll())
        probe({"mode": "stop", "dataset": "uls_private", "expected": selected})
        self.assertEqual(child.wait(timeout=10), -15)


if __name__ == "__main__":
    unittest.main()
