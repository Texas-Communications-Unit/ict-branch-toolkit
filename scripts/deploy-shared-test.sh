#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 || ! "$1" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Usage: deploy-shared-test.sh <40-character-main-commit>" >&2
  exit 2
fi

expected_sha="$1"
app_dir="$HOME/apps/ict-branch-toolkit"
env_file="$HOME/.config/ict-branch-toolkit/deployment.env"
backup_dir="$HOME/backups/ict-branch-toolkit"
compose=(docker compose --env-file "$env_file" -f compose.production.yaml)

cd "$app_dir"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Refusing deployment because the server checkout has uncommitted changes." >&2
  exit 1
fi

git fetch --prune origin main
remote_sha="$(git rev-parse origin/main)"
if [[ "$remote_sha" != "$expected_sha" ]]; then
  echo "Refusing deployment because the requested commit is not current origin/main." >&2
  exit 1
fi

"${compose[@]}" config --quiet

install -d -m 700 "$backup_dir"
backup_file="$backup_dir/postgresql-$(date -u +%Y%m%dT%H%M%SZ)-pre-${expected_sha:0:12}.dump"

set -a
# shellcheck disable=SC1090
source "$env_file"
set +a

"${compose[@]}" exec -T \
  -e PGPASSWORD="$POSTGRES_PASSWORD" \
  db \
  pg_dump \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --format custom > "$backup_file"

chmod 600 "$backup_file"
test -s "$backup_file"

"${compose[@]}" exec -T db sh -c '
  temporary_backup="$(mktemp)"
  trap "rm -f \"$temporary_backup\"" EXIT
  cat > "$temporary_backup"
  pg_restore --list "$temporary_backup" >/dev/null
' < "$backup_file"

git switch main
git merge --ff-only "$expected_sha"

"${compose[@]}" config --quiet
"${compose[@]}" build
"${compose[@]}" up --detach --wait

printf 'Deployed commit %s with backup %s\n' "$expected_sha" "$backup_file"
