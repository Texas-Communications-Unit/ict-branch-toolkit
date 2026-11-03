"""Run the real deployment shell against disposable HOME and fake Docker/Git."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

MOCK = r"""
import json
import os
import pathlib
import sys

args = sys.argv[1:]
tool = pathlib.Path(sys.argv[0]).name
trace = pathlib.Path(os.environ["SYNTHETIC_TRACE"])
with trace.open("a") as stream:
    stream.write(json.dumps([tool, args]) + "\n")
state = pathlib.Path(os.environ["SYNTHETIC_STATE"])
mode = os.environ["SYNTHETIC_MODE"]
if tool == "git":
    if args[:1] == ["rev-parse"]:
        print("b" * 40 if args[-1] == "origin/main" else state.read_text())
    elif args[:1] == ["merge"]:
        state.write_text("b" * 40)
    elif "--detach" in args:
        state.write_text(args[-1])
elif tool == "df":
    print("Filesystem 1024-blocks Used Available Capacity Mounted on")
    print("synthetic 16777216 1 8388608 1% /")
elif tool == "docker":
    if args[:1] == ["compose"]:
        if "--images" in args:
            if mode != "empty-images":
                print("synthetic-db\nsynthetic-backend\nsynthetic-frontend")
        elif "--format" in args:
            print("{}")
        elif "build" in args and mode == "build-failure":
            sys.exit(7)
    elif args[:1] == ["run"]:
        scans = [json.loads(line) for line in trace.read_text().splitlines()]
        scans = [item for item in scans if item[0] == "docker" and item[1][:1] == ["run"]]
        if len(scans) == 2 and mode == "finding":
            sys.exit(1)
        if mode == "scanner-error":
            sys.exit(2)
"""


@unittest.skipUnless(os.name == "posix" and shutil.which("flock"), "Requires Linux shell tools")
class DeploymentPreflightTests(unittest.TestCase):
    def exercise(self, mode):
        with tempfile.TemporaryDirectory(prefix="ict-security-fixture-") as temporary:
            root = Path(temporary)
            application = root / "apps/ict-branch-toolkit"
            application.mkdir(parents=True)
            (application / "compose.production.yaml").write_text("services: {}\n")
            configuration = root / ".config/ict-branch-toolkit"
            configuration.mkdir(parents=True)
            (configuration / "deployment.env").write_text("POSTGRES_PASSWORD=synthetic-only\n")
            scripts = root / "scripts"
            scripts.mkdir()
            shutil.copyfile(
                Path(__file__).with_name("deploy-shared-test.sh"), scripts / "deploy.sh"
            )
            (scripts / "deployment-recovery-set.py").write_text(
                "import os; print(os.environ['SYNTHETIC_BACKUP'])\n"
            )
            (scripts / "validate-compose-environment.py").write_text(
                "import json, sys; json.load(sys.stdin)\n"
            )
            binaries = root / "bin"
            binaries.mkdir()
            for name in ("git", "docker", "df"):
                binary = binaries / name
                binary.write_text(f"#!{sys.executable}\n" + MOCK)
                binary.chmod(0o700)
            state = root / "state"
            state.write_text("a" * 40)
            trace = root / "trace.jsonl"
            result = subprocess.run(
                ["bash", str(scripts / "deploy.sh"), "b" * 40],
                env={
                    **os.environ,
                    "HOME": str(root),
                    "PATH": str(binaries) + os.pathsep + os.environ["PATH"],
                    "SYNTHETIC_TRACE": str(trace),
                    "SYNTHETIC_STATE": str(state),
                    "SYNTHETIC_MODE": mode,
                    "SYNTHETIC_BACKUP": str(root / "synthetic.dump"),
                },
                text=True,
                capture_output=True,
                timeout=30,
            )
            calls = [json.loads(line) for line in trace.read_text().splitlines()]
            promoted = any(tool == "docker" and "up" in args for tool, args in calls)
            scans = [args for tool, args in calls if tool == "docker" and args[:1] == ["run"]]
            if mode == "success":
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(promoted)
                self.assertEqual(len(scans), 3)
                self.assertEqual(state.read_text(), "b" * 40)
                for scan in scans:
                    self.assertIn("HIGH,CRITICAL", scan)
                    self.assertEqual(scan[scan.index("--exit-code") + 1], "1")
            else:
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(promoted, result.stdout)
                self.assertEqual(state.read_text(), "a" * 40)

    def test_only_all_clean_images_allow_container_replacement(self):
        self.exercise("success")

    def test_failed_preparation_preserves_old_checkout_and_containers(self):
        for mode in ("build-failure", "finding", "scanner-error", "empty-images"):
            with self.subTest(mode=mode):
                self.exercise(mode)


if __name__ == "__main__":
    unittest.main()
