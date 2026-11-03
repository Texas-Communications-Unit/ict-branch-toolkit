#!/usr/bin/env python3
"""Synthetic FCC transport tests: no Azure, Docker, or live records."""

import ast
import base64
import gzip
import importlib.util
import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "azure_fcc_sync", Path(__file__).with_name("azure-fcc-sync.py")
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def unpack(wrapper):
    program = shlex.split(wrapper.split("/usr/bin/python3 -c ", 1)[1])[0]
    encoded = ast.literal_eval(program.splitlines()[0].split("=", 1)[1].strip())
    return json.loads(gzip.decompress(base64.b64decode(encoded)))


def program(payload):
    encoded = base64.b64encode(gzip.compress(json.dumps(payload).encode())).decode()
    return f"PAYLOAD = {encoded!r}\n" + MODULE.GUEST_PROGRAM


class FCCTransportTests(unittest.TestCase):
    def test_invalid_inputs_cannot_form_a_guest_command(self):
        for changes in (
            {"sha": "main"},
            {"run": "1;id"},
            {"user": "root"},
            {"user": "$(id)"},
            {"dataset": "asr;id"},
        ):
            values = dict(
                sha="b" * 40,
                run="123-1",
                user="synthetic",
                directory=Path("missing"),
                check_only=True,
            )
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                MODULE.make_script(**(values | changes))

    def test_check_only_excludes_import_download_and_backup(self):
        payload = unpack(
            MODULE.make_script(
                "b" * 40, "123-1", "synthetic", Path("missing"), check_only=True
            )
        )
        self.assertTrue(payload["check_only"])
        data = base64.b64decode(payload["data"]).decode()
        self.assertIn("git rev-parse HEAD", data)
        self.assertIn("ps --status running --services", data)
        for operation in ("import_fcc_archive", "curl ", "pg_dump", "--apply"):
            self.assertNotIn(operation, data)

    def test_transport_uses_fcc_budget_and_does_not_inherit_deploy_budget(self):
        config = {"DEPLOY_USER": "synthetic"}
        for check_only, remote, poll in ((False, 10200, 10440), (True, 180, 600)):
            with tempfile.TemporaryDirectory() as temporary:
                helpers = Path(temporary)
                (helpers / MODULE.HELPER).write_text("# synthetic")
                with (
                    patch.object(
                        MODULE, "make_script", return_value="synthetic wrapper"
                    ),
                    patch.object(MODULE.TRANSPORT, "execute_script") as execute,
                ):
                    MODULE.sync(config, "b" * 40, "123-1", "asr", check_only)
                self.assertEqual(execute.call_args.kwargs["command_prefix"], "ict-fcc")
                self.assertEqual(execute.call_args.kwargs["remote_timeout"], remote)
                self.assertEqual(execute.call_args.kwargs["poll_timeout"], poll)
                self.assertLess(MODULE.GUEST_TIMEOUT + 60, MODULE.REMOTE_TIMEOUT)
                self.assertLess(MODULE.POLL_TIMEOUT, 180 * 60)

    def test_main_rejects_non_main_before_azure_requests(self):
        with (
            patch.dict(os.environ, {"GITHUB_REF": "refs/heads/synthetic"}),
            patch.object(sys, "argv", ["azure-fcc-sync.py", "--check-only"]),
            patch.object(MODULE.TRANSPORT, "execute_script") as execute,
        ):
            self.assertEqual(MODULE.main(), 1)
            execute.assert_not_called()

    @unittest.skipUnless(os.name == "posix", "Guest payload requires Linux bash")
    def test_guest_executes_exact_helper_in_order_and_keeps_output_private(self):
        for code in (0, 7):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                helpers = root / "helpers"
                helpers.mkdir()
                (helpers / MODULE.HELPER).write_text(
                    '#!/bin/bash\nset -eu\necho "private synthetic output"\n'
                    f'test "$2" = "{"b" * 40}"\n'
                    'test "$ICT_FCC_DEADLINE_EPOCH" -gt "$(date +%s)"\n'
                    'echo "$1" >> "$HOME/selected.txt"\n'
                    f"exit {code}\n"
                )
                payload = unpack(
                    MODULE.make_script("b" * 40, "123-2", "synthetic", helpers)
                )
                result = subprocess.run(
                    [sys.executable, "-c", program(payload)],
                    env={**os.environ, "HOME": str(root)},
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                self.assertEqual(
                    result.returncode, 0 if code == 0 else 1, result.stderr
                )
                expected = list(MODULE.DATASETS) if code == 0 else ["asr"]
                self.assertEqual(
                    (root / "selected.txt").read_text().splitlines(), expected
                )
                self.assertNotIn(
                    "private synthetic output", result.stdout + result.stderr
                )
                cache = root / ".cache/ict-branch-toolkit"
                log = cache / "fcc-sync-logs/123-2.log"
                self.assertIn("private synthetic output", log.read_text())
                self.assertEqual(log.stat().st_mode & 0o777, 0o600)
                self.assertFalse(list(cache.glob("fcc-azure-*")))

    @unittest.skipUnless(os.name == "posix", "Guest payload requires Linux bash")
    def test_tampered_helper_never_executes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payload = unpack(
                MODULE.make_script(
                    "b" * 40, "123-1", "synthetic", root, check_only=True
                )
            )
            payload["data"] = base64.b64encode(b'touch "$HOME/unexpected"\n').decode()
            result = subprocess.run(
                [sys.executable, "-c", program(payload)],
                env={**os.environ, "HOME": str(root)},
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((root / "unexpected").exists())

    @unittest.skipUnless(os.name == "posix", "Guest payload requires Linux bash")
    def test_timeout_terminates_guest_process_group_and_preserves_log(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / MODULE.HELPER).write_text(
                "#!/bin/bash\ntrap 'echo \"synthetic termination\"; exit 143' TERM\nsleep 30\n"
            )
            payload = unpack(
                MODULE.make_script("b" * 40, "123-1", "synthetic", root, "asr")
            )
            payload["guest_timeout"] = 0.5
            result = subprocess.run(
                [sys.executable, "-c", program(payload)],
                env={**os.environ, "HOME": str(root)},
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertNotEqual(result.returncode, 0)
            cache = root / ".cache/ict-branch-toolkit"
            self.assertIn(
                "synthetic termination", (cache / "fcc-sync-logs/123-1.log").read_text()
            )
            self.assertFalse(list(cache.glob("fcc-azure-*")))


if __name__ == "__main__":
    unittest.main()
