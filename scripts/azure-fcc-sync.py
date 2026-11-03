#!/usr/bin/env python3
"""Run approved FCC synchronization through the VM-scoped Azure identity."""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from uuid import UUID

SPEC = importlib.util.spec_from_file_location(
    "azure_transport", Path(__file__).with_name("azure-deploy.py")
)
TRANSPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TRANSPORT)

DATASETS = ("asr", "uls_commercial", "uls_private")
HELPER = "sync-fcc-shared-test.sh"
# Keep guest work/cleanup inside Azure's budget and Azure polling inside the
# workflow's 180-minute job. These are deliberately longer than app deployment.
GUEST_TIMEOUT = 9900
REMOTE_TIMEOUT = 10200
POLL_TIMEOUT = 10440

PREFLIGHT = r"""#!/bin/bash
set -euo pipefail
app_dir="$HOME/apps/ict-branch-toolkit"
test -r "$HOME/.config/ict-branch-toolkit/deployment.env"
cd "$app_dir"
test "$(git rev-parse HEAD)" = "$1"
test -z "$(git status --porcelain)"
docker compose --env-file "$HOME/.config/ict-branch-toolkit/deployment.env" \
  -f compose.production.yaml config --quiet
services="$(docker compose --env-file "$HOME/.config/ict-branch-toolkit/deployment.env" \
  -f compose.production.yaml ps --status running --services)"
for service in db backend frontend; do
  grep -qx "$service" <<< "$services"
done
"""

GUEST_PROGRAM = r"""
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time

os.umask(0o077)
payload = json.loads(gzip.decompress(base64.b64decode(PAYLOAD, validate=True)))
data = base64.b64decode(payload["data"], validate=True)
if hashlib.sha256(data).hexdigest() != payload["sha256"]:
    raise ValueError("FCC helper checksum mismatch")
cache = Path.home() / ".cache/ict-branch-toolkit"
cache.mkdir(parents=True, exist_ok=True, mode=0o700)
scripts = Path(tempfile.mkdtemp(prefix="fcc-azure-", dir=cache))
logs = cache / "fcc-sync-logs"
logs.mkdir(exist_ok=True, mode=0o700)
log = logs / (payload["run"] + ".log")
deadline = time.monotonic() + payload["guest_timeout"]
# Bound the import inside the container before the outer process-group timeout.
environment = {**os.environ, "ICT_FCC_DEADLINE_EPOCH": str(int(time.time()) + payload["guest_timeout"] - 120)}
try:
    helper = scripts / "sync-fcc-shared-test.sh"
    helper.write_bytes(data)
    with log.open("x") as output:
        datasets = ("verify",) if payload["check_only"] else payload["datasets"]
        for dataset in datasets:
            command = ["/bin/bash", str(helper)]
            if not payload["check_only"]:
                command.append(dataset)
            command.append(payload["sha"])
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError("FCC synchronization deadline elapsed")
            process = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT,
                                       env=environment, start_new_session=True)
            try:
                code = process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=60)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                raise RuntimeError("FCC synchronization deadline elapsed") from None
            if code:
                print("FCC operation failed; inspect the private FCC sync log before retrying.", flush=True)
                sys.exit(1)
    print("FCC preflight verified; no import performed." if payload["check_only"]
          else "Selected FCC synchronization completed.", flush=True)
finally:
    shutil.rmtree(scripts)
"""


def make_script(
    sha: str,
    run: str,
    user: str,
    directory: Path,
    dataset: str = "all",
    check_only: bool = False,
) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("Expected the exact reviewed main commit")
    if not re.fullmatch(r"[0-9]+-[0-9]+", run):
        raise ValueError("Expected GitHub run ID and attempt")
    if not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", user) or user == "root":
        raise ValueError("Invalid deployment account")
    if dataset not in (*DATASETS, "all"):
        raise ValueError("Unsupported FCC dataset")
    data = PREFLIGHT.encode() if check_only else (directory / HELPER).read_bytes()
    payload = {
        "sha": sha,
        "run": run,
        "check_only": check_only,
        "guest_timeout": 120 if check_only else GUEST_TIMEOUT,
        "datasets": list(DATASETS) if dataset == "all" else [dataset],
        "data": base64.b64encode(data).decode(),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    encoded = base64.b64encode(
        gzip.compress(json.dumps(payload).encode(), mtime=0)
    ).decode()
    program = f"PAYLOAD = {encoded!r}\n" + GUEST_PROGRAM
    return (
        "#!/bin/bash\nset -euo pipefail\n"
        f'deploy_home="$(getent passwd {shlex.quote(user)} | cut -d: -f6)"\n'
        'test -n "$deploy_home" && test -d "$deploy_home"\n'
        f"exec /usr/sbin/runuser -u {shlex.quote(user)} -- /usr/bin/env -i "
        'HOME="$deploy_home" PATH=/usr/local/bin:/usr/bin:/bin LANG=C.UTF-8 '
        f"/usr/bin/python3 -c {shlex.quote(program)}\n"
    )


def sync(config, sha, run, dataset="all", check_only=False):
    TRANSPORT.execute_script(
        config,
        make_script(
            sha, run, config["DEPLOY_USER"], Path(__file__).parent, dataset, check_only
        ),
        run,
        command_prefix="ict-fcc",
        remote_timeout=180 if check_only else REMOTE_TIMEOUT,
        poll_timeout=600 if check_only else POLL_TIMEOUT,
        operation="FCC synchronization",
        log_directory="fcc-sync-logs",
        success_message=(
            "Azure FCC preflight verified without importing data."
            if check_only
            else f"Azure verified FCC synchronization for commit {sha}."
        ),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--dataset", choices=(*DATASETS, "all"), default="all")
    args = parser.parse_args()
    try:
        if os.environ.get("GITHUB_REF") != "refs/heads/main":
            raise ValueError("FCC operations require main")
        config = TRANSPORT.configuration(dict(os.environ))
        if args.validate_only:
            for key in ("AZURE_CLIENT_ID", "AZURE_TENANT_ID"):
                UUID(os.environ.get(key, ""))
            print("Azure FCC configuration is valid.")
            return 0
        sync(
            config,
            os.environ.get("GITHUB_SHA", ""),
            f"{os.environ.get('GITHUB_RUN_ID', '')}-{os.environ.get('GITHUB_RUN_ATTEMPT', '')}",
            args.dataset,
            args.check_only,
        )
        return 0
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        print(
            str(error)
            if isinstance(error, RuntimeError)
            else "Invalid FCC configuration or Azure transport failure.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
