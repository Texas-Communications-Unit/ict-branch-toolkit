#!/usr/bin/env python3
"""Deliver the scanned deployment helpers through Azure, never public SSH."""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import quote
from uuid import UUID

API_VERSION = "2025-04-01"
SCRIPT_NAMES = (
    "deploy-shared-test.sh",
    "validate-compose-environment.py",
    "deployment-recovery-set.py",
)
REMOTE_TIMEOUT = 3000
POLL_TIMEOUT = 3300
TERMINAL_STATES = {"Succeeded", "Failed", "TimedOut", "Canceled"}

# This program runs as the deployment account. Full logs stay private on the VM.
GUEST_PROGRAM = r"""
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

os.umask(0o077)
payload = json.loads(gzip.decompress(base64.b64decode(PAYLOAD)))
home = Path.home()
cache = home / ".cache/ict-branch-toolkit"
cache.mkdir(parents=True, exist_ok=True, mode=0o700)
scripts = Path(tempfile.mkdtemp(prefix="deploy-azure-", dir=cache))
logs = cache / "deployment-logs"
logs.mkdir(exist_ok=True, mode=0o700)
log = logs / (payload["run"] + ".log")
try:
    for name, item in payload["files"].items():
        if name not in ALLOWED_NAMES:
            raise ValueError("Unexpected deployment helper")
        data = base64.b64decode(item["data"], validate=True)
        if hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ValueError("Deployment helper checksum mismatch")
        (scripts / name).write_bytes(data)
    with log.open("x") as output:
        result = subprocess.run(
            ["/bin/bash", str(scripts / "deploy-shared-test.sh"), payload["sha"]],
            stdout=output, stderr=subprocess.STDOUT, check=False,
        )
    if result.returncode:
        print("Deployment failed. Review the private deployment-account log.", flush=True)
        sys.exit(1)
    print("Deployed scanned commit " + payload["sha"], flush=True)
finally:
    shutil.rmtree(scripts)
"""


def configuration(environ: dict[str, str]) -> dict[str, str]:
    result = {}
    for key in (
        "AZURE_SUBSCRIPTION_ID",
        "AZURE_RESOURCE_GROUP",
        "AZURE_VM_NAME",
        "DEPLOY_USER",
    ):
        result[key] = environ.get(key, "").strip()
        if not result[key]:
            raise ValueError(f"Missing {key}")
    UUID(result["AZURE_SUBSCRIPTION_ID"])
    for key in ("AZURE_RESOURCE_GROUP", "AZURE_VM_NAME"):
        if not re.fullmatch(r"[A-Za-z0-9_.()-]{1,90}", result[key]):
            raise ValueError(f"Invalid {key}")
    if not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", result["DEPLOY_USER"]):
        raise ValueError("Invalid DEPLOY_USER")
    if result["DEPLOY_USER"] == "root":
        raise ValueError("Deployment account must not be root")
    return result


def make_script(sha: str, run: str, user: str, directory: Path) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("Expected the exact scanned commit SHA")
    if not re.fullmatch(r"[0-9]+-[0-9]+", run):
        raise ValueError("Expected GitHub run ID and attempt")
    if not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", user) or user == "root":
        raise ValueError("Invalid deployment account")
    files = {}
    for name in SCRIPT_NAMES:
        data = (directory / name).read_bytes()
        files[name] = {
            "data": base64.b64encode(data).decode(),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    payload = base64.b64encode(
        gzip.compress(
            json.dumps({"sha": sha, "run": run, "files": files}).encode(), mtime=0
        )
    ).decode()
    program = (
        f"PAYLOAD = {payload!r}\nALLOWED_NAMES = {SCRIPT_NAMES!r}\n" + GUEST_PROGRAM
    )
    # The agent switches user before processing the embedded deployment helpers.
    return (
        "#!/bin/bash\nset -euo pipefail\n"
        f'deploy_home="$(getent passwd {shlex.quote(user)} | cut -d: -f6)"\n'
        'test -n "$deploy_home" && test -d "$deploy_home"\n'
        f"exec /usr/sbin/runuser -u {shlex.quote(user)} -- /usr/bin/env -i "
        'HOME="$deploy_home" PATH=/usr/local/bin:/usr/bin:/bin LANG=C.UTF-8 '
        f"/usr/bin/python3 -c {shlex.quote(program)}\n"
    )


def az_json(*args: str) -> dict:
    # Azure error bodies may contain script text or infrastructure identifiers.
    result = subprocess.run(
        ["az", *args, "--only-show-errors", "--output", "json"],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if result.returncode:
        raise RuntimeError(
            "Azure API request failed; check identity permissions and Azure Activity Log."
        )
    return json.loads(result.stdout or "{}")


def execution_result(resource: dict) -> bool | None:
    properties = resource.get("properties", {})
    instance = properties.get("instanceView") or {}
    state = instance.get("executionState")
    if state in TERMINAL_STATES:
        return state == "Succeeded" and instance.get("exitCode") == 0
    if properties.get("provisioningState") in {"Failed", "Canceled"}:
        return False
    # Provisioning success alone does not establish script success.
    return None


def deploy(config: dict[str, str], sha: str, run: str) -> None:
    vm_id = (
        f"/subscriptions/{config['AZURE_SUBSCRIPTION_ID']}/resourceGroups/"
        f"{quote(config['AZURE_RESOURCE_GROUP'], safe='')}/providers/Microsoft.Compute/"
        f"virtualMachines/{quote(config['AZURE_VM_NAME'], safe='')}"
    )
    base = "https://management.azure.com" + vm_id
    vm = az_json(
        "rest", "--method", "get", "--url", f"{base}?api-version={API_VERSION}"
    )
    script = make_script(sha, run, config["DEPLOY_USER"], Path(__file__).parent)
    command = f"{base}/runCommands/ict-deploy-{run}?api-version={API_VERSION}"
    body = {
        "location": vm["location"],
        "properties": {
            "source": {"script": script},
            "asyncExecution": True,
            "timeoutInSeconds": REMOTE_TIMEOUT,
            "treatFailureAsDeploymentFailure": True,
        },
    }
    with tempfile.TemporaryDirectory(prefix="ict-azure-request-") as temporary:
        path = Path(temporary) / "request.json"
        path.write_text(json.dumps(body), encoding="utf-8")
        path.chmod(0o600)
        az_json("rest", "--method", "put", "--url", command, "--body", f"@{path}")
    print(
        "Azure accepted the deployment command; waiting for its execution result.",
        flush=True,
    )
    deadline = time.monotonic() + POLL_TIMEOUT
    while time.monotonic() < deadline:
        resource = az_json(
            "rest", "--method", "get", "--url", command + "&$expand=instanceView"
        )
        result = execution_result(resource)
        if result is not None:
            if not result:
                raise RuntimeError(
                    f"Azure deployment failed. Review deployment-logs/{run}.log under the deployment account cache; "
                    "check Azure execution status if no log exists."
                )
            print(f"Azure verified successful execution for commit {sha}.", flush=True)
            # Azure limits retained managed commands. Delete only after proven
            # successful guest completion; preserve failures for investigation.
            try:
                az_json("rest", "--method", "delete", "--url", command)
            except (RuntimeError, OSError, subprocess.TimeoutExpired, ValueError):
                print(
                    "Warning: completed Azure command needs administrator retention cleanup.",
                    flush=True,
                )
            return
        time.sleep(15)
    # Never delete a live command or retry blindly: it can still be running.
    raise RuntimeError(
        "Azure result timed out. Check the existing Run Command and service health before retrying."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    try:
        config = configuration(dict(os.environ))
        if args.validate_only:
            for key in ("AZURE_CLIENT_ID", "AZURE_TENANT_ID"):
                UUID(os.environ.get(key, ""))
            print("Azure deployment configuration is valid.")
            return 0
        deploy(
            config,
            os.environ.get("GITHUB_SHA", ""),
            f"{os.environ.get('GITHUB_RUN_ID', '')}-{os.environ.get('GITHUB_RUN_ATTEMPT', '')}",
        )
        return 0
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        if isinstance(error, RuntimeError):
            print(str(error), file=sys.stderr)
        else:
            print(
                "Invalid deployment configuration or Azure transport failure.",
                file=sys.stderr,
            )
        return 1


if __name__ == "__main__":
    sys.exit(main())
