#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: probe-fcc-shared-test.sh <asr|uls_private|uls_commercial>" >&2
  exit 2
fi

dataset="$1"
case "$dataset" in
  asr)
    archive_name="r_tower.zip"
    ;;
  uls_private)
    archive_name="l_LMpriv.zip"
    ;;
  uls_commercial)
    archive_name="l_LMcomm.zip"
    ;;
  *)
    echo "Unsupported FCC dataset: $dataset" >&2
    exit 2
    ;;
esac

app_dir="$HOME/apps/ict-branch-toolkit"
env_file="$HOME/.config/ict-branch-toolkit/deployment.env"
source_url="https://data.fcc.gov/download/pub/uls/complete/$archive_name"
temporary_dir="$(mktemp -d "$HOME/.cache/fcc-capacity-probe.XXXXXX")"
archive_path="$temporary_dir/$archive_name"
container_id=""

cleanup() {
  if [[ -n "$container_id" ]]; then
    docker exec "$container_id" rm -f -- "/tmp/$archive_name" >/dev/null 2>&1 || true
  fi
  rm -rf -- "$temporary_dir"
}
trap cleanup EXIT
chmod 700 "$temporary_dir"

if [[ ! -f "$env_file" ]]; then
  echo "Protected deployment environment file is missing." >&2
  exit 1
fi

cd "$app_dir"
if [[ -n "$(git status --porcelain)" ]]; then
  echo "Refusing operation because the server checkout has uncommitted changes." >&2
  exit 1
fi

python3 - "$source_url" "$archive_path" <<'PY'
import pathlib
import sys
import urllib.request

source_url, destination = sys.argv[1:]
request = urllib.request.Request(source_url, headers={"User-Agent": "ICT-Branch-Toolkit/1.0"})
with urllib.request.urlopen(request, timeout=120) as response:
    if response.status != 200:
        raise RuntimeError(f"FCC download returned HTTP {response.status}")
    with pathlib.Path(destination).open("wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
PY

test -s "$archive_path"
compose=(docker compose --env-file "$env_file" -f compose.production.yaml)
"${compose[@]}" config --quiet
container_id="$("${compose[@]}" ps -q backend)"
if [[ -z "$container_id" ]]; then
  echo "The backend container is not running." >&2
  exit 1
fi

docker cp "$archive_path" "$container_id:/tmp/$archive_name"
probe_output="$(
  "${compose[@]}" exec -T backend \
    python manage.py probe_fcc_archive_capacity "/tmp/$archive_name" --dataset "$dataset"
)"
python3 -c \
  'import json,sys; result=json.loads(sys.stdin.read()); assert result["validated"] is True; assert result["database_writes"] == 0' \
  <<<"$probe_output"
printf '%s\n' "$probe_output"
