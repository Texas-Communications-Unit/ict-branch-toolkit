#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
Usage:
  database-recovery.sh backup [output.dump]
  database-recovery.sh verify <backup.dump>
  database-recovery.sh drill <backup.dump>
  database-recovery.sh restore <backup.dump> RESTORE:<database-name>

Optional environment overrides:
  ICT_APP_DIR
  ICT_DEPLOY_ENV_FILE
  ICT_BACKUP_DIR
  ICT_COMPOSE_FILE
EOF
  exit 2
}

[[ $# -ge 1 ]] || usage

command_name="$1"
shift

app_dir="${ICT_APP_DIR:-$HOME/apps/ict-branch-toolkit}"
env_file="${ICT_DEPLOY_ENV_FILE:-$HOME/.config/ict-branch-toolkit/deployment.env}"
backup_dir="${ICT_BACKUP_DIR:-$HOME/backups/ict-branch-toolkit}"
compose_file="${ICT_COMPOSE_FILE:-$app_dir/compose.production.yaml}"

[[ -d "$app_dir" ]] || {
  echo "Application directory not found: $app_dir" >&2
  exit 1
}
[[ -f "$env_file" ]] || {
  echo "Protected deployment environment file not found: $env_file" >&2
  exit 1
}
[[ -f "$compose_file" ]] || {
  echo "Compose file not found: $compose_file" >&2
  exit 1
}

umask 077
set -a
# shellcheck disable=SC1090
source "$env_file"
set +a

: "${POSTGRES_DB:?POSTGRES_DB is required in the deployment environment file}"
: "${POSTGRES_USER:?POSTGRES_USER is required in the deployment environment file}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required in the deployment environment file}"

compose=(docker compose --env-file "$env_file" -f "$compose_file")
temporary_backup=""

cleanup_temporary_backup() {
  if [[ -n "$temporary_backup" ]]; then
    rm -f -- "$temporary_backup"
  fi
}
trap cleanup_temporary_backup EXIT

cd "$app_dir"
"${compose[@]}" config --quiet

if ! "${compose[@]}" ps --status running --services | grep -qx db; then
  echo "The database service must be running before recovery operations." >&2
  exit 1
fi

verify_catalog() {
  local archive="$1"

  [[ -f "$archive" && ! -L "$archive" && -s "$archive" ]] || {
    echo "Backup is missing or empty: $archive" >&2
    return 1
  }

  # Variables in this command expand inside the database container.
  # shellcheck disable=SC2016
  "${compose[@]}" exec -T db sh -c '
    archive="$(mktemp)"
    trap "rm -f \"$archive\"" EXIT
    cat > "$archive"
    pg_restore --list "$archive" >/dev/null
  ' < "$archive"
}

verify_archive() {
  local archive="$1"
  local archive_name actual_checksum checksum_name expected_checksum

  verify_catalog "$archive"
  archive_name="$(basename "$archive")"

  [[ -f "$archive.sha256" && ! -L "$archive.sha256" ]] || {
    echo "Checksum file is missing: $archive.sha256" >&2
    return 1
  }
  read -r expected_checksum checksum_name < "$archive.sha256"
  [[ "$checksum_name" == "$archive_name" ]] || {
    echo "Checksum file does not name the requested backup: $archive" >&2
    return 1
  }
  actual_checksum="$(sha256sum "$archive" | awk '{print $1}')"
  [[ "$actual_checksum" == "$expected_checksum" ]] || {
    echo "Backup checksum verification failed: $archive" >&2
    return 1
  }
}

create_backup() {
  local destination="$1"
  local destination_dir destination_name partial

  destination_dir="$(dirname "$destination")"
  install -d -m 700 "$destination_dir"
  destination_dir="$(cd "$destination_dir" && pwd)"
  destination_name="$(basename "$destination")"
  destination="$destination_dir/$destination_name"
  partial="$destination.partial.$$"

  [[ ! -e "$destination" && ! -e "$destination.sha256" ]] || {
    echo "Refusing to overwrite an existing backup or checksum: $destination" >&2
    return 1
  }

  temporary_backup="$partial"

  "${compose[@]}" exec -T \
    -e PGPASSWORD="$POSTGRES_PASSWORD" \
    db \
    pg_dump \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    --format custom \
    --no-owner \
    --no-privileges > "$partial"

  verify_catalog "$partial"
  mv "$partial" "$destination"
  (
    cd "$destination_dir"
    sha256sum "$destination_name" > "$destination_name.sha256"
  )
  chmod 600 "$destination" "$destination.sha256"
  verify_archive "$destination"
  temporary_backup=""

  printf '%s\n' "$destination"
}

case "$command_name" in
  backup)
    [[ $# -le 1 ]] || usage
    install -d -m 700 "$backup_dir"
    output="${1:-$backup_dir/postgresql-$(date -u +%Y%m%dT%H%M%SZ).dump}"
    create_backup "$output"
    ;;

  verify)
    [[ $# -eq 1 ]] || usage
    verify_archive "$1"
    printf 'Verified backup archive and checksum: %s\n' "$1"
    ;;

  drill)
    [[ $# -eq 1 ]] || usage
    archive="$1"
    verify_archive "$archive"
    drill_database="ict_recovery_drill_$(date -u +%Y%m%d%H%M%S)_$$"

    cleanup_drill() {
      cleanup_temporary_backup
      "${compose[@]}" exec -T \
        -e PGPASSWORD="$POSTGRES_PASSWORD" \
        db \
        dropdb \
        --username "$POSTGRES_USER" \
        --force \
        --if-exists \
        "$drill_database" >/dev/null
    }
    trap cleanup_drill EXIT

    cleanup_drill
    "${compose[@]}" exec -T \
      -e PGPASSWORD="$POSTGRES_PASSWORD" \
      db \
      createdb \
      --username "$POSTGRES_USER" \
      --owner "$POSTGRES_USER" \
      "$drill_database"

    # Variables in this command expand inside the database container.
    # shellcheck disable=SC2016
    "${compose[@]}" exec -T \
      -e PGPASSWORD="$POSTGRES_PASSWORD" \
      -e RECOVERY_DATABASE="$drill_database" \
      db sh -c '
        archive="$(mktemp)"
        trap "rm -f \"$archive\"" EXIT
        cat > "$archive"
        pg_restore \
          --exit-on-error \
          --no-owner \
          --no-privileges \
          --username "$POSTGRES_USER" \
          --dbname "$RECOVERY_DATABASE" \
          "$archive"
        migration_count="$(
          psql \
            --username "$POSTGRES_USER" \
            --dbname "$RECOVERY_DATABASE" \
            --tuples-only \
            --no-align \
            --command "SELECT COUNT(*) FROM django_migrations"
        )"
        test "$migration_count" -gt 0
      ' < "$archive"

    printf 'Restore drill passed in isolated database %s.\n' "$drill_database"
    ;;

  restore)
    [[ $# -eq 2 ]] || usage
    archive="$1"
    confirmation="$2"
    expected_confirmation="RESTORE:$POSTGRES_DB"
    [[ "$confirmation" == "$expected_confirmation" ]] || {
      echo "Restore refused. Required confirmation: $expected_confirmation" >&2
      exit 1
    }

    verify_archive "$archive"
    install -d -m 700 "$backup_dir"
    emergency_backup="$backup_dir/postgresql-$(date -u +%Y%m%dT%H%M%SZ)-pre-restore.dump"
    emergency_backup="$(create_backup "$emergency_backup")"

    "${compose[@]}" stop backend frontend

    "${compose[@]}" exec -T \
      -e PGPASSWORD="$POSTGRES_PASSWORD" \
      db \
      dropdb \
      --username "$POSTGRES_USER" \
      --force \
      "$POSTGRES_DB"
    "${compose[@]}" exec -T \
      -e PGPASSWORD="$POSTGRES_PASSWORD" \
      db \
      createdb \
      --username "$POSTGRES_USER" \
      --owner "$POSTGRES_USER" \
      "$POSTGRES_DB"

    # Variables in this command expand inside the database container.
    # shellcheck disable=SC2016
    "${compose[@]}" exec -T \
      -e PGPASSWORD="$POSTGRES_PASSWORD" \
      db sh -c '
        archive="$(mktemp)"
        trap "rm -f \"$archive\"" EXIT
        cat > "$archive"
        pg_restore \
          --exit-on-error \
          --no-owner \
          --no-privileges \
          --username "$POSTGRES_USER" \
          --dbname "$POSTGRES_DB" \
          "$archive"
      ' < "$archive"

    "${compose[@]}" up --detach --wait backend frontend
    printf 'Database restored from %s. Emergency backup: %s\n' \
      "$archive" "$emergency_backup"
    ;;

  *)
    usage
    ;;
esac
