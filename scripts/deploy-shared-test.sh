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

if [[ ! -f "$env_file" ]]; then
  echo "Refusing deployment because the protected environment file is missing." >&2
  exit 1
fi

resolved_env="$(mktemp)"
cleanup() {
  rm -f "$resolved_env"
}
trap cleanup EXIT
chmod 600 "$resolved_env"

# Preserve protected server settings while applying the approved public basemap
# and checksum-pinned NIFOG 2.02 reference configuration.
grep -v -e '^VITE_MAP_' -e '^ICT_APPROVED_REFERENCE_IMPORTS=' "$env_file" > "$resolved_env"
cat >> "$resolved_env" <<'EOF'
ICT_APPROVED_REFERENCE_IMPORTS=[{"source_type":"cisa_nifog","version":"2.02","authoritative_url":"https://www.cisa.gov/sites/default/files/2024-12/NIFOG%202.02_508%20FINAL%20VERSION%2012%2003%202024.pdf","content_sha256":"45c2f5d94861b3ed1b80f7ce5962a160fdd56092211586bdee711b68ca3d3142"}]
VITE_MAP_STYLE_URL=
VITE_MAP_TILE_URL=https://tile.openstreetmap.org/{z}/{x}/{y}.png
VITE_MAP_PROVIDER_ID=osm-standard
VITE_MAP_PROVIDER_NAME=OpenStreetMap standard tiles
VITE_MAP_ATTRIBUTION_TEXT=© OpenStreetMap contributors
VITE_MAP_ATTRIBUTION_URL=https://www.openstreetmap.org/copyright
VITE_MAP_LICENSE_NAME=Open Database License 1.0
VITE_MAP_LICENSE_URL=https://opendatacommons.org/licenses/odbl/1-0/
VITE_MAP_TERMS_URL=https://operations.osmfoundation.org/policies/tiles/
VITE_MAP_PRIVACY_URL=https://osmfoundation.org/wiki/Privacy_Policy
VITE_MAP_REPORT_ISSUE_URL=https://www.openstreetmap.org/fixthemap
VITE_MAP_CONTACT_URL=https://github.com/Texas-Communications-Unit/ict-branch-toolkit/issues
EOF

compose=(docker compose --env-file "$resolved_env" -f compose.production.yaml)

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
