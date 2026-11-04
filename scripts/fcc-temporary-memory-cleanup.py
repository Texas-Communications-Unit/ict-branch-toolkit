#!/usr/bin/env python3
"""Remove only an explicitly named, idle, root-owned temporary FCC swap file."""

import argparse
import datetime
import json
import os
import re
import stat
import subprocess
import time
from pathlib import Path


def validate_target(target, directory, *, expected_bytes=32 * 1024**3, expected_uid=0):
    target, directory = Path(target), Path(directory)
    if target.is_symlink() or target.resolve().parent != directory.resolve():
        raise ValueError("temporary_resource_path_refused")
    if not re.fullmatch(r"fcc-import-[0-9]{8}\.swap", target.name):
        raise ValueError("temporary_resource_name_refused")
    metadata = target.stat()
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or metadata.st_uid != expected_uid
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or metadata.st_size != expected_bytes
    ):
        raise ValueError("temporary_resource_metadata_refused")
    return metadata


def active_imports():
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            args = (entry / "cmdline").read_bytes().decode().split("\0")
            if (
                len(args) > 2
                and Path(args[1]).name == "manage.py"
                and args[2] == "import_fcc_archive"
            ):
                return True
        except (OSError, UnicodeError):
            continue
    return False


def remove_when_idle(args):
    import fcntl

    target, record = Path(args.swap_path), Path(args.record)
    if not target.exists():
        return
    if (
        record.is_symlink()
        or record.stat().st_uid != 0
        or record.stat().st_mode & 0o077
    ):
        raise ValueError("untrusted_temporary_resource_record")
    evidence = json.loads(record.read_text())
    if (
        evidence.get("fstab_modified", False)
        or str(target) in Path("/etc/fstab").read_text()
    ):
        raise ValueError("persistent_swap_configuration_requires_review")
    with Path(args.maintenance_lock).open("r+") as lock:
        end = time.monotonic() + args.wait_seconds
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                pass
            else:
                if not active_imports():
                    break
                fcntl.flock(lock, fcntl.LOCK_UN)
            if time.monotonic() >= end:
                raise TimeoutError("temporary_resource_still_busy")
            time.sleep(30)
        before = validate_target(target, args.allowed_directory)
        entries = [
            line.split() for line in Path("/proc/swaps").read_text().splitlines()[1:]
        ]
        active = [entry for entry in entries if entry[0] == str(target)]
        if active:
            available = int(
                next(
                    line.split()[1]
                    for line in Path("/proc/meminfo").read_text().splitlines()
                    if line.startswith("MemAvailable:")
                )
            )
            if available <= int(active[0][3]) + 524288:
                raise MemoryError("insufficient_memory_for_safe_swap_removal")
            subprocess.run(["swapoff", str(target)], check=True, timeout=180)
        if any(
            line.split()[0] == str(target)
            for line in Path("/proc/swaps").read_text().splitlines()[1:]
        ):
            raise RuntimeError("temporary_swap_still_active")
        after = validate_target(target, args.allowed_directory)
        if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
            raise ValueError("temporary_resource_identity_changed")
        target.unlink()
        evidence.update(
            status="removed",
            removed_utc=datetime.datetime.now(datetime.UTC).isoformat(),
        )
        temporary = record.with_suffix(".json.tmp")
        with temporary.open("w") as stream:
            temporary.chmod(0o600)
            json.dump(evidence, stream, indent=2)
            stream.write("\n")
        temporary.replace(record)
        print("Temporary FCC swap removed; persistent configuration unchanged.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--swap-path", required=True)
    parser.add_argument("--record", required=True)
    parser.add_argument("--allowed-directory", required=True)
    parser.add_argument("--maintenance-lock", required=True)
    parser.add_argument("--wait-seconds", type=int, default=39600)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    os.umask(0o077)
    try:
        if args.check:
            validate_target(args.swap_path, args.allowed_directory)
            print("Recorded temporary FCC resource metadata verified; no change made.")
        else:
            remove_when_idle(args)
    except (
        OSError,
        ValueError,
        RuntimeError,
        MemoryError,
        TimeoutError,
        subprocess.SubprocessError,
    ) as error:
        print("Temporary FCC resource cleanup failed: " + type(error).__name__)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
