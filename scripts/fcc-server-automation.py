#!/usr/bin/env python3
"""Server-native FCC orchestration. No LLM, GitHub token, or code deployment."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import smtplib
import ssl
import subprocess
import time
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path
from urllib.request import urlopen

ARCHIVES = {
    "asr": "r_tower.zip",
    "uls_commercial": "l_LMcomm.zip",
    "uls_private": "l_LMpriv.zip",
}
PROGRESS = re.compile(
    r"Staged (\d+)/(\d+) (antennastructure|ulslicense|ulslocation|ulsfrequency|ulsemission) records"
)

# This executes inside the existing backend account, without additional capabilities.
# It can lower only a verified import process's limits/priority, never Gunicorn's.
PROCESS_PROGRAM = r"""
import json,os,pathlib,re,resource,signal,sys
request=json.load(sys.stdin); matches=[]; unknown=0
names={'asr':'r_tower.zip','uls_commercial':'l_LMcomm.zip','uls_private':'l_LMpriv.zip'}
for entry in pathlib.Path('/proc').iterdir():
 if not entry.name.isdigit():continue
 try:
  args=(entry/'cmdline').read_bytes().decode().split('\0')
  if len(args)<4 or not pathlib.PurePosixPath(args[0]).name.startswith('python') or pathlib.PurePosixPath(args[1]).name!='manage.py' or args[2]!='import_fcc_archive':continue
  if '--dataset' not in args or '--work-dir' not in args:unknown+=1;continue
  dataset=args[args.index('--dataset')+1]; directory=args[args.index('--work-dir')+1]
  archive=pathlib.PurePosixPath(args[3])
  if dataset not in names or archive.name!=names[dataset] or str(archive.parent)!=directory or not re.fullmatch(r'/tmp/ict-fcc-[A-Za-z0-9]{8}',directory):unknown+=1;continue
  if request.get('dataset') and dataset!=request['dataset']:continue
  fields={line.split(':',1)[0]:line.split(':',1)[1].strip() for line in (entry/'status').read_text().splitlines() if ':' in line}
  start=(entry/'stat').read_text().rsplit(') ',1)[1].split()[19]
  matches.append({'pid':int(entry.name),'start':start,'dataset':dataset,'vm_peak_kib':int(fields.get('VmPeak','0 kB').split()[0]),'rss_peak_kib':int(fields.get('VmHWM','0 kB').split()[0]),'swap_kib':int(fields.get('VmSwap','0 kB').split()[0])})
 except (OSError,UnicodeError,ValueError,IndexError):continue
result={'processes':matches,'unknown_imports':unknown}
if request['mode']!='probe':
 expected=request.get('expected')
 selected=[m for m in matches if not expected or (m['pid']==expected['pid'] and m['start']==expected['start'])]
 if len(selected)!=1 or (unknown and not (request['mode']=='stop' and expected)):result['error']='import_identity_not_unique'
 else:
  selected=selected[0]
  try:
   if request['mode']=='stop':os.kill(selected['pid'],signal.SIGKILL if request.get('force') else signal.SIGTERM)
   elif request['mode']=='limit':
    mib=request['memory_mib']
    if type(mib) is not int or not 256<=mib<=4096:raise ValueError('memory_limit_outside_policy')
    physical=os.sysconf('SC_PHYS_PAGES')*os.sysconf('SC_PAGE_SIZE')
    cgroup=pathlib.Path('/sys/fs/cgroup/memory.max')
    if cgroup.exists() and cgroup.read_text().strip().isdigit():physical=min(physical,int(cgroup.read_text()))
    limit=min(mib*1024**2,physical//2)
    used=int(next(s.split()[1] for s in pathlib.Path('/proc',str(selected['pid']),'status').read_text().splitlines() if s.startswith('VmSize:')))*1024
    if used>=limit:raise ValueError('import_already_exceeds_memory_budget')
    soft,hard=resource.prlimit(selected['pid'],resource.RLIMIT_AS)
    hard=min(hard,limit) if hard!=resource.RLIM_INFINITY else limit
    soft=min(soft,hard) if soft!=resource.RLIM_INFINITY else hard
    resource.prlimit(selected['pid'],resource.RLIMIT_AS,(soft,hard))
    os.setpriority(os.PRIO_PROCESS,selected['pid'],max(10,os.getpriority(os.PRIO_PROCESS,selected['pid'])))
    selected['limit_bytes']=hard
  except (OSError,ValueError) as error:result['error']=type(error).__name__
print(json.dumps(result))
"""

METADATA_PROGRAM = """import os,django,json
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings");django.setup()
from apps.fcc_data.models import FccImportBatch
result={}
for dataset in ('asr','uls_commercial','uls_private'):
 result[dataset]=list(FccImportBatch.objects.filter(dataset=dataset,is_current=True).values('content_sha256','retrieved_at','record_counts')[:2])
print(json.dumps(result,default=str))"""


class JobError(Exception):
    """A safe error code suitable for status/notification output."""


def utc():
    return datetime.now(UTC).isoformat()


def run(command, **kwargs):
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, check=False, **kwargs
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise JobError(type(error).__name__) from None
    if result.returncode:
        raise JobError("command_failed")
    return result.stdout


def load_config(path, *, require_root_owner=True):
    path = Path(path)
    if path.is_symlink() or (require_root_owner and path.stat().st_uid != 0):
        raise JobError("untrusted_configuration_owner")
    if path.stat().st_mode & 0o022:
        raise JobError("writable_configuration")
    config = json.loads(path.read_text())
    for key in ("app_dir", "env_file", "state_dir", "data_dir", "maintenance_lock"):
        if not Path(config[key]).is_absolute():
            raise JobError("configuration_requires_absolute_paths")
    if (
        type(config.get("memory_limit_mib", 4096)) is not int
        or not 256 <= config.get("memory_limit_mib", 4096) <= 4096
    ):
        raise JobError("memory_limit_outside_policy")
    if (
        type(config.get("dataset_timeout_seconds", 9900)) is not int
        or not 120 <= config.get("dataset_timeout_seconds", 9900) <= 9900
    ):
        raise JobError("execution_budget_outside_policy")
    config.setdefault("backend_container", "ict-branch-toolkit-backend-1")
    return config


def save_status(config, name, status):
    directory = Path(config["state_dir"])
    if directory.is_symlink():
        raise JobError("redirected_state_directory")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if directory.stat().st_uid != os.geteuid() or directory.stat().st_mode & 0o077:
        raise JobError("state_directory_permissions")
    target = directory / f"{name}-last.json"
    temporary = directory / f".{name}-{uuid.uuid4().hex}.tmp"
    with temporary.open("x") as stream:
        temporary.chmod(0o600)
        json.dump(status, stream, indent=2)
        stream.write("\n")
    temporary.replace(target)


@contextmanager
def file_lock(path, *, wait_seconds=0):
    import fcntl

    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink():
        raise JobError("redirected_lock")
    end = time.monotonic() + wait_seconds
    with path.open("a+") as stream:
        path.chmod(0o600)
        while True:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= end:
                    raise JobError("maintenance_busy") from None
                time.sleep(min(15, max(0, end - time.monotonic())))
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def process_probe(config, *, mode="probe", dataset=None, expected=None, force=False):
    request = {
        "mode": mode,
        "dataset": dataset,
        "expected": expected,
        "force": force,
        "memory_mib": config.get("memory_limit_mib", 4096),
    }
    output = run(
        [
            "docker",
            "exec",
            "-i",
            config["backend_container"],
            "python",
            "-c",
            PROCESS_PROGRAM,
        ],
        input=json.dumps(request),
        timeout=30,
    )
    return json.loads(output)


def wait_idle(config, *, wait_seconds):
    end = time.monotonic() + wait_seconds
    while True:
        try:
            with file_lock(config["maintenance_lock"]):
                probe = process_probe(config)
                if not probe["processes"] and not probe["unknown_imports"]:
                    return
        except JobError as error:
            if str(error) != "maintenance_busy":
                raise
        if time.monotonic() >= end:
            raise JobError("maintenance_wait_expired")
        time.sleep(15)


def deployed_release(config):
    app = Path(config["app_dir"])
    if run(["git", "-C", str(app), "status", "--porcelain"], timeout=30).strip():
        raise JobError("deployed_checkout_is_dirty")
    sha = run(["git", "-C", str(app), "rev-parse", "HEAD"], timeout=30).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise JobError("invalid_deployed_commit")
    if (
        run(
            ["git", "-C", str(app), "symbolic-ref", "--short", "HEAD"], timeout=30
        ).strip()
        != "main"
    ):
        raise JobError("deployed_release_not_on_main")
    run(
        ["git", "-C", str(app), "merge-base", "--is-ancestor", sha, "origin/main"],
        timeout=30,
    )
    helper = app / "scripts/sync-fcc-shared-test.sh"
    if helper.is_symlink() or not helper.is_file():
        raise JobError("invalid_deployed_helper")
    return sha


def verify_dataset(config, dataset):
    output = run(
        [
            "docker",
            "exec",
            config["backend_container"],
            "python",
            "-c",
            METADATA_PROGRAM,
        ],
        timeout=60,
    )
    batches = json.loads(output)[dataset]
    archive = Path(config["data_dir"]) / ARCHIVES[dataset]
    marker = Path(str(archive) + ".imported.sha256")
    if (
        len(batches) != 1
        or archive.is_symlink()
        or marker.is_symlink()
        or not archive.is_file()
        or not marker.is_file()
    ):
        raise JobError("dataset_verification_missing_or_ambiguous")
    digest = marker.read_text().strip()
    with archive.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if (
        not re.fullmatch(r"[0-9a-f]{64}", digest)
        or batches[0]["content_sha256"] != digest
        or actual != digest
    ):
        raise JobError("dataset_digest_mismatch")
    return batches[0]


def health_check(config):
    with urlopen(
        config["public_base_url"].rstrip("/") + "/api/health/", timeout=20
    ) as response:
        if response.status != 200:
            raise JobError("application_health_check_failed")


def last_progress(path):
    with Path(path).open("rb") as stream:
        stream.seek(max(0, Path(path).stat().st_size - 8192))
        matches = PROGRESS.findall(stream.read().decode("utf-8", errors="replace"))
    if not matches:
        return None
    done, total, collection = matches[-1]
    return {
        "collection": collection,
        "completed": int(done),
        "total": int(total),
        "committed": False,
    }


def stop_import(config, dataset, expected):
    if expected is None:
        return
    process_probe(config, mode="stop", dataset=dataset, expected=expected)
    for _ in range(6):
        time.sleep(5)
        found = process_probe(config, dataset=dataset)["processes"]
        if not any(
            p["pid"] == expected["pid"] and p["start"] == expected["start"]
            for p in found
        ):
            return
    process_probe(config, mode="stop", dataset=dataset, expected=expected, force=True)


def run_dataset(config, dataset, sha, state, job_name):
    wait_idle(config, wait_seconds=config.get("maintenance_wait_seconds", 10800))
    logs = Path(config["state_dir"]) / "logs"
    if logs.is_symlink():
        raise JobError("redirected_log_directory")
    logs.mkdir(mode=0o700, exist_ok=True)
    log = logs / f"{state['run_id']}-{dataset}.log"
    seconds = config.get("dataset_timeout_seconds", 9900)
    environment = {
        **os.environ,
        "ICT_FCC_DEADLINE_EPOCH": str(int(time.time()) + seconds - 60),
    }
    expected = None
    state.update(dataset=dataset, progress=None, updated_at=utc())
    save_status(config, job_name, state)
    with log.open("x") as stream:
        log.chmod(0o600)
        process = subprocess.Popen(
            [
                "/bin/bash",
                str(Path(config["app_dir"]) / "scripts/sync-fcc-shared-test.sh"),
                dataset,
                sha,
            ],
            env=environment,
            stdout=stream,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        end = time.monotonic() + seconds
        try:
            while process.poll() is None:
                if time.monotonic() >= end:
                    raise JobError("dataset_execution_deadline")
                probe = process_probe(config, dataset=dataset)
                if probe["unknown_imports"] or len(probe["processes"]) > 1:
                    raise JobError("import_identity_conflict")
                if probe["processes"]:
                    observed = probe["processes"][0]
                    if expected is None:
                        expected = {"pid": observed["pid"], "start": observed["start"]}
                        limited = process_probe(
                            config, mode="limit", dataset=dataset, expected=expected
                        )
                        if limited.get("error"):
                            if limited["processes"] or limited["unknown_imports"]:
                                raise JobError("import_memory_guard_failed")
                        elif limited["processes"]:
                            observed = limited["processes"][0]
                    elif (
                        observed["pid"] != expected["pid"]
                        or observed["start"] != expected["start"]
                    ):
                        raise JobError("import_identity_changed")
                    state["resource_observation"] = observed
                state.update(progress=last_progress(log), updated_at=utc())
                save_status(config, job_name, state)
                time.sleep(15)
            if process.returncode:
                raise JobError("dataset_helper_failed")
        except BaseException:
            try:
                stop_import(config, dataset, expected)
            except (JobError, OSError, ValueError):
                print(json.dumps({"event": "import_stop_failed"}), flush=True)
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=45)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait(timeout=15)
            raise
    with file_lock(config["maintenance_lock"], wait_seconds=60):
        result = verify_dataset(config, dataset)
        health_check(config)
    state["verified"][dataset] = result
    state.update(progress=None, updated_at=utc())
    save_status(config, job_name, state)


def notify(config, subject, body):
    if not config.get("notifications_enabled", False):
        return False
    compose = json.loads(
        run(
            [
                "docker",
                "compose",
                "--env-file",
                config["env_file"],
                "-f",
                str(Path(config["app_dir"]) / "compose.production.yaml"),
                "config",
                "--format",
                "json",
            ],
            timeout=30,
        )
    )
    settings = compose["services"]["backend"]["environment"]
    if str(settings.get("ICT_EMAIL_ENABLED", "false")).lower() != "true":
        raise JobError("application_mail_not_enabled")
    use_ssl = str(settings.get("DJANGO_EMAIL_USE_SSL", "false")).lower() == "true"
    use_tls = str(settings.get("DJANGO_EMAIL_USE_TLS", "true")).lower() == "true"
    if use_ssl and use_tls:
        raise JobError("conflicting_mail_transport")
    username = settings.get("DJANGO_EMAIL_HOST_USER", "")
    if username and not (use_ssl or use_tls):
        raise JobError("mail_credentials_require_encryption")
    message = EmailMessage()
    message["From"] = settings["DJANGO_DEFAULT_FROM_EMAIL"]
    message["To"] = config["notification_email"]
    message["Subject"] = subject
    message.set_content(body)
    context = ssl.create_default_context()
    options = {"timeout": 30}
    if use_ssl:
        options["context"] = context
    connection = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    with connection(
        settings["DJANGO_EMAIL_HOST"],
        int(settings.get("DJANGO_EMAIL_PORT", 587)),
        **options,
    ) as mail:
        if use_tls:
            mail.starttls(context=context)
        if username:
            mail.login(username, settings.get("DJANGO_EMAIL_HOST_PASSWORD", ""))
        mail.send_message(message)
    return True


def execute(config, args):
    state = {
        "run_id": datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8],
        "status": "running",
        "phase": "waiting_for_maintenance",
        "started_at": utc(),
        "verified": {},
    }
    save_status(config, args.job_name, state)
    try:
        with file_lock(Path(config["state_dir"]) / "controller.lock"):
            wait_idle(
                config, wait_seconds=config.get("maintenance_wait_seconds", 10800)
            )
            sha = deployed_release(config)
            state["application_commit"] = sha
            if args.after_external_log:
                if not re.fullmatch(r"[0-9]{1,20}-[0-9]{1,5}", args.after_external_log):
                    raise JobError("invalid_external_operation")
                log = (
                    Path(config["maintenance_lock"]).parent
                    / "fcc-sync-logs"
                    / f"{args.after_external_log}.log"
                )
                content = log.read_text() if log.stat().st_size < 4 * 1024**2 else ""
                if "FCC temporary cleanup failed" in content or not (
                    f"FCC dataset {args.after_dataset} updated from" in content
                    or f"FCC archive {ARCHIVES[args.after_dataset]} is unchanged at sha256="
                    in content
                ):
                    raise JobError("external_import_did_not_complete_successfully")
                with file_lock(config["maintenance_lock"], wait_seconds=60):
                    state["verified"][args.after_dataset] = verify_dataset(
                        config, args.after_dataset
                    )
            for dataset in ARCHIVES if args.dataset == "all" else (args.dataset,):
                print(
                    json.dumps(
                        {
                            "event": "starting_dataset",
                            "dataset": dataset,
                            "run_id": state["run_id"],
                        }
                    ),
                    flush=True,
                )
                run_dataset(config, dataset, sha, state, args.job_name)
            state.update(status="succeeded", finished_at=utc())
            save_status(config, args.job_name, state)
    except (
        JobError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
        KeyboardInterrupt,
    ) as error:
        state.update(
            status="failed",
            finished_at=utc(),
            error_code=str(error)
            if isinstance(error, JobError)
            else type(error).__name__,
        )
        save_status(config, args.job_name, state)
        raise
    print(
        json.dumps(
            {"event": "finished", "status": "succeeded", "run_id": state["run_id"]}
        ),
        flush=True,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="/etc/ict-toolkit-fcc.json")
    parser.add_argument(
        "--job-name", choices=("weekly", "bootstrap", "manual"), default="weekly"
    )
    parser.add_argument("--dataset", choices=("all", *ARCHIVES), default="all")
    parser.add_argument("--after-external-log")
    parser.add_argument(
        "--after-dataset", choices=tuple(ARCHIVES), default="uls_commercial"
    )
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--notify-test", action="store_true")
    parser.add_argument("--notify-failure", action="store_true")
    args = parser.parse_args(argv)
    os.umask(0o077)
    try:
        config = load_config(args.config)
        if args.notify_test:
            if not notify(
                config,
                "ICT Toolkit FCC automation notification test",
                "FCC synchronization failure notifications are configured. This test contains no credentials or application records.",
            ):
                raise JobError("notifications_disabled")
        elif args.notify_failure:
            path = Path(config["state_dir"]) / f"{args.job_name}-last.json"
            state = (
                json.loads(path.read_text()) if path.exists() else {"status": "failed"}
            )
            if state.get("status") == "running":
                state.update(
                    status="failed", error_code="service_interrupted", finished_at=utc()
                )
            if state.get("notification_sent_at"):
                return 0
            sent = notify(
                config,
                "ICT Toolkit FCC synchronization failed",
                f"FCC synchronization did not finish successfully. Job: {args.job_name}. Check the server's FCC status file and systemd journal. Partial staging is not proof of a published dataset. No credentials or application records are included.",
            )
            state["notification_sent_at" if sent else "notification_disabled_at"] = (
                utc()
            )
            save_status(config, args.job_name, state)
        elif args.check:
            deployed_release(config)
            health_check(config)
            print(
                "FCC automation configuration and deployed application verified; no import performed."
            )
        else:
            execute(config, args)
    except (
        JobError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
        KeyboardInterrupt,
    ) as error:
        code = str(error) if isinstance(error, JobError) else type(error).__name__
        print(json.dumps({"event": "failed", "error_code": code}), flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
