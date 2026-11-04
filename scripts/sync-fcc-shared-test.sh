#!/usr/bin/env bash
set -euo pipefail
umask 077

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: sync-fcc-shared-test.sh <asr|uls_private|uls_commercial> [expected-main-sha]" >&2
  exit 2
fi

dataset="$1"
expected_sha="${2:-}"
if [[ -n "$expected_sha" && ! "$expected_sha" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Expected a full reviewed main commit SHA." >&2
  exit 2
fi
case "$dataset" in
  asr) archive_name="r_tower.zip" ;;
  uls_private) archive_name="l_LMpriv.zip" ;;
  uls_commercial) archive_name="l_LMcomm.zip" ;;
  *) echo "Unsupported FCC dataset: $dataset" >&2; exit 2 ;;
esac

app_dir="$HOME/apps/ict-branch-toolkit"
env_file="$HOME/.config/ict-branch-toolkit/deployment.env"

# A schema upgrade and a reference-data import must not overlap on this host.
install -d -m 700 "$HOME/.cache/ict-branch-toolkit"
exec 9>"$HOME/.cache/ict-branch-toolkit/maintenance.lock"
flock -n 9 || { echo "Another deployment or FCC sync is active; retry later." >&2; exit 1; }
data_dir="$HOME/data/ict-branch-toolkit/fcc"
backup_dir="$HOME/backups/ict-branch-toolkit"
source_url="https://data.fcc.gov/download/pub/uls/complete/$archive_name"
archive_path="$data_dir/$archive_name"
download_path="$archive_path.download"
digest_path="$archive_path.imported.sha256"
container_id=""
container_archive_dir=""
container_archive=""

cleanup() {
  rm -f -- "$download_path"
  if [[ -n "$container_id" && -n "$container_archive_dir" ]]; then
    docker exec "$container_id" sh -c 'rm -f -- "$1"; rmdir -- "$2"' \
      sh "$container_archive" "$container_archive_dir" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT
trap 'exit 143' TERM

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

if [[ -n "$expected_sha" && "$(git rev-parse HEAD)" != "$expected_sha" ]]; then
  echo "Refusing FCC import because the deployed commit differs from reviewed main." >&2
  exit 1
fi

deadline="${ICT_FCC_DEADLINE_EPOCH:-$(($(date +%s) + 9900))}"
if [[ ! "$deadline" =~ ^[0-9]{1,12}$ ]]; then
  echo "Invalid FCC execution deadline." >&2
  exit 2
fi
remaining_seconds() {
  local remaining
  remaining=$((deadline - $(date +%s)))
  if (( remaining <= 0 )); then
    echo "FCC execution deadline elapsed; inspect the existing operation before retrying." >&2
    return 1
  fi
  printf '%s\n' "$remaining"
}

download_timeout="$(remaining_seconds)"
curl --fail --location --retry 4 --retry-all-errors --connect-timeout 30 \
  --proto '=https' --proto-redir '=https' \
  --max-time "$download_timeout" --retry-max-time "$download_timeout" \
  --user-agent "ICT-Branch-Toolkit/1.0 (toolkit@tx-comu.org)" \
  --output "$download_path" "$source_url"
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

# docker cp creates a root-owned file even when the image runs as a non-root
# account. Stream through that account into its own private temporary directory.
container_archive_dir="$(docker exec "$container_id" mktemp -d /tmp/ict-fcc-XXXXXXXX)"
if [[ ! "$container_archive_dir" =~ ^/tmp/ict-fcc-[A-Za-z0-9]{8}$ ]]; then
  container_archive_dir=""
  echo "Backend returned an invalid private archive directory." >&2
  exit 1
fi
container_archive="$container_archive_dir/$archive_name"
docker exec -i "$container_id" sh -c 'umask 077; cat > "$1"' sh "$container_archive" \
  < "$archive_path"
probe_timeout="$(remaining_seconds)"
probe_output="$(
  "${compose[@]}" exec -T backend \
    timeout --signal=TERM --kill-after=30s "$probe_timeout" \
      python manage.py probe_fcc_archive_capacity "$container_archive" --dataset "$dataset"
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
import_timeout="$(remaining_seconds)"
"${compose[@]}" exec -T backend \
  timeout --signal=TERM --kill-after=30s "$import_timeout" \
    env PGOPTIONS='-c client_connection_check_interval=1s' \
    python manage.py import_fcc_archive "$container_archive" \
    --dataset "$dataset" --source-url "$source_url" --username "$actor" --apply

digest_temporary="$digest_path.tmp"
printf '%s\n' "$download_digest" > "$digest_temporary"
chmod 600 "$digest_temporary"
mv -f -- "$digest_temporary" "$digest_path"
printf 'FCC dataset %s updated from %s with backup %s.\n' \
  "$dataset" "$archive_path" "$backup_file"
