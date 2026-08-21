#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: sync-fcc-shared-test.sh <asr|uls_private|uls_commercial>" >&2
  exit 2
fi

dataset="$1"
case "$dataset" in
  asr) archive_name="r_tower.zip" ;;
  uls_private) archive_name="l_LMpriv.zip" ;;
  uls_commercial) archive_name="l_LMcomm.zip" ;;
  *) echo "Unsupported FCC dataset: $dataset" >&2; exit 2 ;;
esac

app_dir="$HOME/apps/ict-branch-toolkit"
env_file="$HOME/.config/ict-branch-toolkit/deployment.env"
data_dir="$HOME/data/ict-branch-toolkit/fcc"
backup_dir="$HOME/backups/ict-branch-toolkit"
source_url="https://data.fcc.gov/download/pub/uls/complete/$archive_name"
archive_path="$data_dir/$archive_name"
download_path="$archive_path.download"
digest_path="$archive_path.imported.sha256"
container_id=""

cleanup() {
  rm -f -- "$download_path"
  if [[ -n "$container_id" ]]; then
    docker exec "$container_id" rm -f -- "/tmp/$archive_name" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

if [[ ! -f "$env_file" ]]; then
  echo "Protected deployment environment file is missing." >&2
  exit 1
fi
install -d -m 700 "$data_dir" "$backup_dir"
cd "$app_dir"
if [[ -n "$(git status --porcelain)" ]]; then
  echo "Refusing update because the server checkout has uncommitted changes." >&2
  exit 1
fi

python3 - "$source_url" "$download_path" <<'PY'
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
test -s "$download_path"
download_digest="$(sha256sum "$download_path" | cut -d ' ' -f 1)"
mv -f -- "$download_path" "$archive_path"
chmod 600 "$archive_path"

if [[ -f "$digest_path" ]] && [[ "$(cat "$digest_path")" == "$download_digest" ]]; then
  printf 'FCC archive %s is unchanged at sha256=%s; no database write required.\n' \
    "$archive_name" "$download_digest"
  exit 0
fi

compose=(docker compose --env-file "$env_file" -f compose.production.yaml)
"${compose[@]}" config --quiet
container_id="$("${compose[@]}" ps -q backend)"
if [[ -z "$container_id" ]]; then
  echo "The backend container is not running." >&2
  exit 1
fi

backup_file="$backup_dir/postgresql-$(date -u +%Y%m%dT%H%M%SZ)-pre-fcc-$dataset.dump"
# shellcheck disable=SC2016
"${compose[@]}" exec -T db sh -c '
  export PGPASSWORD="$POSTGRES_PASSWORD"
  exec pg_dump --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --format custom
' > "$backup_file"
chmod 600 "$backup_file"
test -s "$backup_file"
sha256sum "$backup_file" > "$backup_file.sha256"
chmod 600 "$backup_file.sha256"
"${compose[@]}" exec -T db pg_restore --list < "$backup_file" >/dev/null

docker cp "$archive_path" "$container_id:/tmp/$archive_name"
probe_output="$(
  "${compose[@]}" exec -T backend \
    python manage.py probe_fcc_archive_capacity "/tmp/$archive_name" --dataset "$dataset"
)"
python3 -c \
  'import json,sys; result=json.loads(sys.stdin.read()); assert result["validated"] is True; assert result["database_writes"] == 0' \
  <<<"$probe_output"
printf '%s\n' "$probe_output"

actor="$(docker exec "$container_id" printenv DJANGO_SUPERUSER_USERNAME)"
if [[ -z "$actor" ]]; then
  echo "The configured administrator username is empty." >&2
  exit 1
fi
"${compose[@]}" exec -T backend \
  python manage.py import_fcc_archive "/tmp/$archive_name" \
    --dataset "$dataset" --source-url "$source_url" --username "$actor" --apply

digest_temporary="$digest_path.tmp"
printf '%s\n' "$download_digest" > "$digest_temporary"
chmod 600 "$digest_temporary"
mv -f -- "$digest_temporary" "$digest_path"
printf 'FCC dataset %s updated from %s with backup %s.\n' \
  "$dataset" "$archive_path" "$backup_file"
