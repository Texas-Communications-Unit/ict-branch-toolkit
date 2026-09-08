#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 || ! "$1" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Usage: deploy-shared-test.sh <40-character-main-commit> [--go-live-reset]" >&2
  exit 2
fi
if [[ ${2:-} != "" && ${2:-} != "--go-live-reset" ]]; then
  echo "The optional second argument must be --go-live-reset." >&2
  exit 2
fi

expected_sha="$1"
go_live_reset=${2:-}
app_dir="$HOME/apps/ict-branch-toolkit"
env_file="$HOME/.config/ict-branch-toolkit/deployment.env"
backup_dir="$HOME/backups/ict-branch-toolkit"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
environment_validator="$script_dir/validate-compose-environment.py"
backup_retention_count=5
build_reserve_kb=$((4 * 1024 * 1024))

available_kb() {
  df -Pk "$1" | awk 'NR==2 {print $4}'
}

show_disk_diagnostics() {
  echo "Filesystem usage:" >&2
  df -h "$HOME" "$backup_dir" 2>/dev/null >&2 || df -h "$HOME" >&2 || true
  echo "Docker disk usage:" >&2
  docker system df >&2 || true
}

if [[ ! -f "$env_file" ]]; then
  echo "Refusing deployment because the protected environment file is missing." >&2
  exit 1
fi
if [[ ! -f "$environment_validator" ]]; then
  echo "Refusing deployment because the environment validator is missing." >&2
  exit 1
fi

resolved_env="$(mktemp)"
cleanup() {
  rm -f "$resolved_env"
}
trap cleanup EXIT
chmod 600 "$resolved_env"

# Preserve protected server settings while applying approved public data sources.
# Remove every overridden key so an older value cannot take precedence.
grep -v \
  -e '^VITE_MAP_' \
  -e '^ICT_APPROVED_REFERENCE_IMPORTS=' \
  -e '^ICT_ELEVATION_PROVIDER=' \
  -e '^ICT_APPROVED_ELEVATION_SOURCES=' \
  -e '^ICT_GEOCODER_PROVIDER=' \
  -e '^ICT_TERRAIN_PROVIDER=' \
  -e '^ICT_APPROVED_TERRAIN_CONFIGURATIONS=' \
  "$env_file" > "$resolved_env"
cat >> "$resolved_env" <<'EOF'
ICT_APPROVED_REFERENCE_IMPORTS=[{"source_type":"cisa_nifog","version":"2.02","authoritative_url":"https://www.cisa.gov/sites/default/files/2024-12/NIFOG%202.02_508%20FINAL%20VERSION%2012%2003%202024.pdf","content_sha256":"45c2f5d94861b3ed1b80f7ce5962a160fdd56092211586bdee711b68ca3d3142"}]
ICT_GEOCODER_PROVIDER=apps.sites.geocoders.CensusGeocoder
ICT_ELEVATION_PROVIDER=apps.rf_analysis.elevation.USGS3DEPElevationProvider
ICT_APPROVED_ELEVATION_SOURCES=[{"provider":"usgs-3dep-epqs","dataset_product":"USGS 3D Elevation Program dynamic elevation service","horizontal_crs":"NAD83 geographic coordinates requested as WKID 4326","vertical_crs":"NAVD 88 over CONUS; source-dependent outside CONUS","target_vertical_crs":"source vertical reference retained without transformation","resolution_m":"10.000","source_version":"EPQS API v1; dynamic 3DEP current at retrieval","license_terms_url":"https://www.usgs.gov/faqs/are-there-any-costs-or-restrictions-usage-data-downloaded-national-map","permitted_use":"Public-domain USGS National Map data; planning decision support with source accuracy and vertical-reference limitations retained.","coverage":{"service":"USGS 3DEP","primary_region":"United States and territories"},"source_content_sha256":"f15a6bcf89f3e2cba37b4b59e223ef13f2f07336ad1fb7661e502016ed133d17","offline":false}]
ICT_TERRAIN_PROVIDER=apps.rf_analysis.terrain.USGS3DEPTerrainProfileProvider
ICT_APPROVED_TERRAIN_CONFIGURATIONS=[{"provider":"usgs-3dep-epqs","provider_version":"terrain-profile-provider-v1","dataset_product":"USGS 3D Elevation Program dynamic elevation service","dataset_version":"EPQS API v1; dynamic 3DEP current at retrieval","source_content_sha256":"4c49a378bace4d22a4409ffa8c36de285edc330b5453856b5cff2bbdc24d03f0","engine":"provisional_sampled_line_of_sight","engine_version":"sampled-line-of-sight-v1-provisional"}]
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
"${compose[@]}" config --format json | python3 "$environment_validator"

install -d -m 700 "$backup_dir"

# Remove incomplete backup files from prior failed deployments. A complete backup
# always has its matching checksum file; partial dumps have no rollback value.
find "$backup_dir" -maxdepth 1 -type f -name 'postgresql-*.dump' -print0 \
  | while IFS= read -r -d '' candidate; do
      if [[ ! -f "$candidate.sha256" ]]; then
        echo "Removing incomplete pre-deployment backup: $candidate"
        rm -f -- "$candidate"
      fi
    done

# Retain the newest verified backups. Before creating a new backup, keep at most
# retention_count-1 existing backups so the completed new backup becomes the newest
# member of the retained set. Only checksum-verified backups are eligible for removal.
python3 - "$backup_dir" "$backup_retention_count" <<'PY'
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

backup_dir = Path(sys.argv[1])
retention_count = int(sys.argv[2])
keep_existing = max(retention_count - 1, 0)

def verified(path: Path) -> bool:
    checksum_path = Path(f"{path}.sha256")
    if not checksum_path.is_file():
        return False
    expected = checksum_path.read_text().split()[0]
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest() == expected

backups = sorted(
    backup_dir.glob("postgresql-*.dump"),
    key=lambda path: path.stat().st_mtime,
    reverse=True,
)
verified_backups = [path for path in backups if verified(path)]
for old_backup in verified_backups[keep_existing:]:
    checksum = Path(f"{old_backup}.sha256")
    print(f"Removing expired verified pre-deployment backup: {old_backup}")
    old_backup.unlink()
    checksum.unlink(missing_ok=True)
PY

# Require enough free capacity for approximately one uncompressed database-size
# equivalent plus a 1 GiB safety margin before starting pg_dump.
# shellcheck disable=SC2016
db_size_bytes="$("${compose[@]}" exec -T db sh -c '
  export PGPASSWORD="$POSTGRES_PASSWORD"
  exec psql \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    --tuples-only --no-align \
    --command "SELECT pg_database_size(current_database());"
')"
if [[ ! "$db_size_bytes" =~ ^[0-9]+$ ]]; then
  echo "Refusing deployment because database size could not be determined." >&2
  show_disk_diagnostics
  exit 1
fi
required_backup_kb=$((db_size_bytes / 1024 + 1024 * 1024))
free_backup_kb="$(available_kb "$backup_dir")"
if (( free_backup_kb < required_backup_kb )); then
  printf 'Refusing deployment: backup filesystem has %s KiB free; at least %s KiB is required for the pre-deployment database backup.\n' \
    "$free_backup_kb" "$required_backup_kb" >&2
  show_disk_diagnostics
  exit 1
fi

backup_file="$backup_dir/postgresql-$(date -u +%Y%m%dT%H%M%SZ)-pre-${expected_sha:0:12}.dump"

# Read the database credentials from the already-running database container.
# Importing the protected environment into Bash would alter quoted JSON values
# and can override the exact values that Compose validated above.
# shellcheck disable=SC2016
if ! "${compose[@]}" exec -T db sh -c '
  export PGPASSWORD="$POSTGRES_PASSWORD"
  exec pg_dump \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    --format custom
' > "$backup_file"; then
  rm -f -- "$backup_file" "$backup_file.sha256"
  show_disk_diagnostics
  exit 1
fi

chmod 600 "$backup_file"
test -s "$backup_file"
(
  cd "$backup_dir"
  sha256sum "$(basename "$backup_file")" > "$(basename "$backup_file").sha256"
)
chmod 600 "$backup_file.sha256"

# shellcheck disable=SC2016
"${compose[@]}" exec -T db sh -c '
  temporary_backup="$(mktemp)"
  trap "rm -f \"$temporary_backup\"" EXIT
  cat > "$temporary_backup"
  pg_restore --list "$temporary_backup" >/dev/null
' < "$backup_file"

# The image build needs working room independent of the database backup. Stop
# before changing the checkout if the host cannot maintain a 4 GiB reserve.
free_build_kb="$(available_kb "$app_dir")"
if (( free_build_kb < build_reserve_kb )); then
  printf 'Refusing deployment: only %s KiB is free after backup; at least %s KiB is required before image builds.\n' \
    "$free_build_kb" "$build_reserve_kb" >&2
  show_disk_diagnostics
  exit 1
fi

git switch main
git merge --ff-only "$expected_sha"

"${compose[@]}" config --quiet
"${compose[@]}" config --format json | python3 "$environment_validator"
"${compose[@]}" build
if "${compose[@]}" up --detach --wait; then
  :
else
  compose_status=$?
  printf 'Deployment startup failed with exit code %s. Container status follows.\n' \
    "$compose_status" >&2
  "${compose[@]}" ps --all >&2 || true
  printf 'Recent backend logs follow. Protected environment values are not displayed.\n' >&2
  "${compose[@]}" logs --no-color --timestamps --tail 200 backend >&2 || true
  exit "$compose_status"
fi

if [[ "$go_live_reset" == "--go-live-reset" ]]; then
  verified_backup_sha256="$(awk '{print $1}' "$backup_file.sha256")"
  "${compose[@]}" exec -T backend python manage.py purge_incident_data \
    --confirm DELETE-ALL-INCIDENT-DATA \
    --verified-backup-sha256 "$verified_backup_sha256"
fi

printf 'Deployed commit %s with backup %s and checksum %s\n' \
  "$expected_sha" "$backup_file" "$backup_file.sha256"
