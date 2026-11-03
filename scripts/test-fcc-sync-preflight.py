#!/usr/bin/env python3
"""Exercise FCC host guards with synthetic commands and temporary files only."""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("sync-fcc-shared-test.sh")

FAKE_TOOL = r"""
import json
import os
from pathlib import Path
import sys
tool = Path(sys.argv[0]).name
args = sys.argv[1:]
home = Path(os.environ["HOME"])
def event(value):
    with (home / "events.jsonl").open("a") as stream:
        stream.write(json.dumps(value) + "\n")
if tool == "git":
    if args == ["status", "--porcelain"]:
        print("synthetic dirty" if os.environ.get("SYNTHETIC_DIRTY") else "")
    elif args == ["rev-parse", "HEAD"]:
        print(os.environ.get("SYNTHETIC_SHA", "b" * 40))
    else:
        sys.exit(2)
elif tool == "curl":
    assert args[args.index("--proto") + 1] == "=https"
    assert args[args.index("--proto-redir") + 1] == "=https"
    event({"operation": "download"})
    Path(args[args.index("--output") + 1]).write_bytes(b"synthetic archive")
elif tool == "docker":
    if args[:1] == ["cp"] or args[:2] == ["exec", "synthetic-container"]:
        if "printenv" in args:
            print("synthetic-actor")
    elif args[0] == "compose":
        if "config" in args:
            pass
        elif "ps" in args:
            print("synthetic-container")
        elif "db" in args:
            if "sh" in args:
                sys.stdout.buffer.write(b"synthetic database dump")
        elif "backend" in args:
            assert "timeout" in args, "Container operation must have its own timeout"
            duration = int(args[args.index("--kill-after=30s") + 1])
            assert duration > 0
            if "probe_fcc_archive_capacity" in args:
                event({"operation": "probe", "timeout": duration})
                print(json.dumps({"validated": True, "database_writes": 0}))
            elif "import_fcc_archive" in args:
                assert "PGOPTIONS=-c client_connection_check_interval=1s" in args
                event({"operation": "import", "timeout": duration})
                sys.exit(int(os.environ.get("SYNTHETIC_IMPORT_EXIT", "0")))
            else:
                sys.exit(2)
        else:
            sys.exit(2)
    else:
        sys.exit(2)
else:
    sys.exit(2)
"""


@unittest.skipUnless(os.name == "posix", "Host helper requires Linux bash")
class FCCPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "apps/ict-branch-toolkit").mkdir(parents=True)
        env = self.root / ".config/ict-branch-toolkit/deployment.env"
        env.parent.mkdir(parents=True)
        env.write_text("# synthetic configuration only\n")
        binaries = self.root / "bin"
        binaries.mkdir()
        controller = binaries / "tool.py"
        controller.write_text(f"#!{sys.executable}\n" + FAKE_TOOL)
        controller.chmod(0o700)
        for tool in ("git", "curl", "docker"):
            (binaries / tool).symlink_to(controller)
        self.environment = {
            **os.environ,
            "HOME": str(self.root),
            "PATH": str(binaries) + os.pathsep + os.environ["PATH"],
            "ICT_FCC_DEADLINE_EPOCH": str(int(time.time()) + 120),
        }

    def run_helper(self, **changes):
        return subprocess.run(
            ["bash", str(SCRIPT), "asr", "b" * 40],
            env=self.environment | changes,
            capture_output=True,
            text=True,
            timeout=15,
        )

    def events(self):
        path = self.root / "events.jsonl"
        return (
            [json.loads(line) for line in path.read_text().splitlines()]
            if path.exists()
            else []
        )

    def test_dirty_or_wrong_commit_cannot_download_or_import(self):
        for changes in ({"SYNTHETIC_DIRTY": "1"}, {"SYNTHETIC_SHA": "c" * 40}):
            with self.subTest(changes=changes):
                self.assertNotEqual(self.run_helper(**changes).returncode, 0)
                self.assertEqual(self.events(), [])

    def test_expired_deadline_fails_before_download(self):
        self.assertNotEqual(self.run_helper(ICT_FCC_DEADLINE_EPOCH="1").returncode, 0)
        self.assertEqual(self.events(), [])

    def test_capacity_wrapper_requires_confirmation_before_host_access(self):
        environment = {
            key: value
            for key, value in self.environment.items()
            if key != "ICT_CAPACITY_CONFIRMATION"
        }
        result = subprocess.run(
            [
                "bash",
                str(SCRIPT.with_name("run-shared-test-capacity.sh")),
                "b" * 40,
                "123",
                "1",
            ],
            env=environment,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("RUN-SYNTHETIC-CAPACITY", result.stderr)
        self.assertEqual(self.events(), [])

    def test_confirmed_capacity_run_refuses_an_active_maintenance_lock(self):
        import fcntl

        lock = self.root / ".cache/ict-branch-toolkit/maintenance.lock"
        lock.parent.mkdir(parents=True)
        with lock.open("w") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = subprocess.run(
                [
                    "bash",
                    str(SCRIPT.with_name("run-shared-test-capacity.sh")),
                    "b" * 40,
                    "123",
                    "1",
                ],
                env=self.environment
                | {"ICT_CAPACITY_CONFIRMATION": "RUN-SYNTHETIC-CAPACITY"},
                capture_output=True,
                text=True,
                timeout=10,
            )
        self.assertEqual(result.returncode, 1)
        self.assertIn("maintenance", result.stderr)
        self.assertEqual(self.events(), [])

    def test_success_is_private_bounded_and_unchanged_archive_skips_import(self):
        for _ in range(2):
            result = self.run_helper()
            self.assertEqual(result.returncode, 0, result.stderr)
        events = self.events()
        self.assertEqual(
            [e["operation"] for e in events],
            ["download", "probe", "import", "download"],
        )
        for e in events:
            if "timeout" in e:
                self.assertLessEqual(e["timeout"], 120)
        backup = next((self.root / "backups/ict-branch-toolkit").glob("*.dump"))
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        self.assertTrue(Path(str(backup) + ".sha256").exists())
        self.assertTrue(
            (
                self.root / "data/ict-branch-toolkit/fcc/r_tower.zip.imported.sha256"
            ).exists()
        )

    def test_failed_import_does_not_advance_digest_marker(self):
        result = self.run_helper(SYNTHETIC_IMPORT_EXIT="7")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(
            (
                self.root / "data/ict-branch-toolkit/fcc/r_tower.zip.imported.sha256"
            ).exists()
        )
        self.assertEqual(
            [e["operation"] for e in self.events()], ["download", "probe", "import"]
        )
        self.assertTrue(list((self.root / "backups/ict-branch-toolkit").glob("*.dump")))


if __name__ == "__main__":
    unittest.main()
