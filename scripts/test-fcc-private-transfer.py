#!/usr/bin/env python3
"""Prove private FCC staging works without root or capabilities; synthetic only."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend-image", required=True)
    args = parser.parse_args()
    name = "fcc-private-transfer-" + uuid.uuid4().hex[:12]

    def docker(*arguments, **kwargs):
        return subprocess.run(
            ["docker", *arguments],
            check=True,
            capture_output=True,
            timeout=90,
            **kwargs,
        ).stdout

    try:
        docker(
            "run",
            "-d",
            "--name",
            name,
            "--network",
            "none",
            "--user",
            "10001:10001",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--entrypoint",
            "sleep",
            args.backend_image,
            "120",
        )
        data = b"synthetic FCC archive bytes only\n"
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "synthetic.zip"
            source.write_bytes(data)
            source.chmod(0o600)
            docker("cp", str(source), name + ":/tmp/root-owned.zip")
        # Exercise the original failure so a looser test image cannot hide it.
        docker(
            "exec",
            "-i",
            name,
            "python",
            "-",
            input=b"""
from pathlib import Path
try:
    Path('/tmp/root-owned.zip').read_bytes()
except PermissionError:
    pass
else:
    raise AssertionError('Fixture did not reproduce private root-owned archive failure')
""",
        )
        directory = (
            docker("exec", name, "mktemp", "-d", "/tmp/ict-fcc-XXXXXXXX")
            .decode()
            .strip()
        )
        archive = directory + "/synthetic.zip"
        docker(
            "exec",
            "-i",
            name,
            "sh",
            "-c",
            'umask 077; cat > "$1"',
            "sh",
            archive,
            input=data,
        )
        result = docker(
            "exec",
            name,
            "python",
            "-c",
            """
import hashlib,json,os,sys
from pathlib import Path
p=Path(sys.argv[1]); s=p.stat()
assert s.st_uid==os.getuid()==10001
assert s.st_mode & 0o777==0o600
assert p.parent.stat().st_mode & 0o777==0o700
status=Path('/proc/self/status').read_text()
assert 'NoNewPrivs:\\t1' in status
print(json.dumps({'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}))
""",
            archive,
        )
        assert json.loads(result)["sha256"] == hashlib.sha256(data).hexdigest()
        print(
            "Private archive staging passed with non-root ownership, mode 0600, and no privileges."
        )
    finally:
        subprocess.run(
            ["docker", "rm", "-f", "-v", name], capture_output=True, timeout=30
        )


if __name__ == "__main__":
    main()
