#!/usr/bin/env python3
"""Synthetic Azure transport checks; never contact Azure or deploy an app."""

import ast
import base64
import gzip
import importlib.util
import json
import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "azure_deploy", Path(__file__).with_name("azure-deploy.py")
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AzureDeploymentTests(unittest.TestCase):
    def config(self):
        return {
            "AZURE_SUBSCRIPTION_ID": "00000000-0000-0000-0000-000000000001",
            "AZURE_RESOURCE_GROUP": "synthetic-group",
            "AZURE_VM_NAME": "synthetic-vm",
            "DEPLOY_USER": "synthetic",
        }

    def test_invalid_or_privileged_account_rejected(self):
        for value in ("root", "user;id", "$(id)", "", "user/name"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                MODULE.configuration({**self.config(), "DEPLOY_USER": value})

    def test_provisioning_success_is_not_execution_success(self):
        self.assertIsNone(
            MODULE.execution_result({"properties": {"provisioningState": "Succeeded"}})
        )
        self.assertIsNone(
            MODULE.execution_result(
                {"properties": {"instanceView": {"executionState": "Running"}}}
            )
        )

    def test_connection_check_excludes_real_deployment_helpers(self):
        wrapper = MODULE.make_script(
            "b" * 40, "123-1", "synthetic", Path("missing-directory"), True
        )
        program = shlex.split(wrapper.split("/usr/bin/python3 -c ", 1)[1])[0]
        encoded = ast.literal_eval(program.splitlines()[0].split("=", 1)[1].strip())
        payload = json.loads(gzip.decompress(base64.b64decode(encoded)))
        self.assertTrue(payload["check_only"])
        helpers = [
            base64.b64decode(item["data"]).decode()
            for item in payload["files"].values()
        ]
        self.assertIn('test "$(id -un)" = synthetic', helpers[0])
        self.assertFalse(
            any(
                command in "\n".join(helpers)
                for command in ("docker", "git ", "manage.py")
            )
        )

    def test_only_success_with_zero_exit_is_accepted(self):
        for state, code, expected in (
            ("Succeeded", 0, True),
            ("Succeeded", 1, False),
            ("Succeeded", None, False),
            ("Failed", 0, False),
            ("TimedOut", 0, False),
            ("Canceled", 0, False),
        ):
            with self.subTest(state=state, code=code):
                self.assertIs(
                    MODULE.execution_result(
                        {
                            "properties": {
                                "instanceView": {
                                    "executionState": state,
                                    "exitCode": code,
                                }
                            }
                        }
                    ),
                    expected,
                )

    def test_exact_scanned_helpers_delivered_and_errors_propagated(self):
        if os.name != "posix":
            self.skipTest("Guest payload requires Linux bash")
        for code in (0, 7):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                helpers = root / "helpers"
                helpers.mkdir()
                (helpers / MODULE.SCRIPT_NAMES[0]).write_text(
                    '#!/bin/bash\necho "private synthetic output"\n'
                    f'test "$1" = "{"b" * 40}" || exit 9\nexit {code}\n'
                )
                for name in MODULE.SCRIPT_NAMES[1:]:
                    (helpers / name).write_text("# synthetic helper\n")
                wrapper = MODULE.make_script("b" * 40, "123-2", "synthetic", helpers)
                # Execute only the user-space Python payload, never runuser/root.
                program = shlex.split(wrapper.split("/usr/bin/python3 -c ", 1)[1])[0]
                result = subprocess.run(
                    ["python3", "-c", program],
                    env={**os.environ, "HOME": str(root)},
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(
                    result.returncode, 0 if code == 0 else 1, result.stderr
                )
                self.assertNotIn(
                    "private synthetic output", result.stdout + result.stderr
                )
                cache = root / ".cache/ict-branch-toolkit"
                log = cache / "deployment-logs/123-2.log"
                self.assertIn("private synthetic output", log.read_text())
                self.assertEqual(log.stat().st_mode & 0o777, 0o600)
                self.assertFalse(list(cache.glob("deploy-azure-*")))

    def test_transport_polls_execution_not_provisioning(self):
        requests = []

        def request(*args):
            requests.append(args)
            if args[2] == "put":
                body = json.loads(Path(args[-1][1:]).read_text())
                self.assertEqual(body["properties"]["timeoutInSeconds"], 3000)
                return {"properties": {"provisioningState": "Succeeded"}}
            if "$expand=instanceView" in args[-1]:
                return {
                    "properties": {
                        "instanceView": {"executionState": "Succeeded", "exitCode": 0}
                    }
                }
            return {"location": "synthetic-region"}

        with patch.object(MODULE, "az_json", side_effect=request):
            MODULE.deploy(self.config(), "b" * 40, "123-1")
        self.assertEqual(len(requests), 4)
        self.assertIn("/runCommands/ict-deploy-123-1", requests[1][4])
        self.assertEqual(requests[-1][2], "delete")

    def test_cleanup_error_does_not_misreport_success(self):
        with patch.object(
            MODULE,
            "az_json",
            side_effect=[
                {"location": "synthetic-region"},
                {},
                {
                    "properties": {
                        "instanceView": {"executionState": "Succeeded", "exitCode": 0}
                    }
                },
                RuntimeError("synthetic cleanup failure"),
            ],
        ):
            MODULE.deploy(self.config(), "b" * 40, "123-1")

    def test_failed_guest_fails_deployment(self):
        responses = [
            {"location": "synthetic-region"},
            {},
            {
                "properties": {
                    "instanceView": {"executionState": "Failed", "exitCode": 7}
                }
            },
        ]
        with (
            patch.object(MODULE, "az_json", side_effect=responses),
            self.assertRaises(RuntimeError),
        ):
            MODULE.deploy(self.config(), "b" * 40, "123-1")

    def test_timeout_does_not_delete_running_command(self):
        with (
            patch.object(
                MODULE, "az_json", side_effect=[{"location": "synthetic-region"}, {}]
            ) as api,
            patch.object(MODULE.time, "monotonic", side_effect=[0, 4000]),
            self.assertRaisesRegex(RuntimeError, "Check the existing Run Command"),
        ):
            MODULE.deploy(self.config(), "b" * 40, "123-1")
        self.assertEqual(api.call_count, 2)


if __name__ == "__main__":
    unittest.main()
