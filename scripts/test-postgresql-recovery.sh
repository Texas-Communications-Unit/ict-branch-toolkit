#!/bin/sh
set -eu

: "${PGHOST:?PGHOST is required}"
: "${PGPORT:?PGPORT is required}"
: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${PGPASSWORD:?PGPASSWORD is required}"

umask 077
temporary_dir="$(mktemp -d)"
archive="$temporary_dir/recovery-test.dump"
drill_database="ict_recovery_ci_${GITHUB_RUN_ID:-local}_$$"

cleanup() {
  psql \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    --command "DROP TABLE IF EXISTS public.ict_recovery_probe" \
    >/dev/null 2>&1 || true
  dropdb --force --if-exists --username "$POSTGRES_USER" "$drill_database" \
    >/dev/null 2>&1 || true
  rm -rf "$temporary_dir"
}
trap cleanup EXIT

psql \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --command "DROP TABLE IF EXISTS public.ict_recovery_probe" \
  >/dev/null
psql \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --command "CREATE TABLE public.ict_recovery_probe (value text NOT NULL)" \
  >/dev/null
psql \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --command "INSERT INTO public.ict_recovery_probe VALUES ('synthetic-recovery-marker')" \
  >/dev/null

pg_dump \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --format custom \
  --no-owner \
  --no-privileges \
  --file "$archive"

test -s "$archive"
sha256sum "$archive" > "$archive.sha256"
sha256sum -c -s "$archive.sha256"
pg_restore --list "$archive" >/dev/null
psql \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --command "DROP TABLE public.ict_recovery_probe" \
  >/dev/null

createdb \
  --username "$POSTGRES_USER" \
  --owner "$POSTGRES_USER" \
  "$drill_database"
pg_restore \
  --exit-on-error \
  --no-owner \
  --no-privileges \
  --username "$POSTGRES_USER" \
  --dbname "$drill_database" \
  "$archive"

source_migrations="$(
  psql \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    --tuples-only \
    --no-align \
    --command "SELECT COUNT(*) FROM django_migrations"
)"
restored_migrations="$(
  psql \
    --username "$POSTGRES_USER" \
    --dbname "$drill_database" \
    --tuples-only \
    --no-align \
    --command "SELECT COUNT(*) FROM django_migrations"
)"

test "$source_migrations" -gt 0
test "$restored_migrations" -eq "$source_migrations"
restored_postgis="$(
  psql \
    --username "$POSTGRES_USER" \
    --dbname "$drill_database" \
    --tuples-only \
    --no-align \
    --command "SELECT PostGIS_Version()"
)"
test -n "$restored_postgis"
restored_marker="$(
  psql \
    --username "$POSTGRES_USER" \
    --dbname "$drill_database" \
    --tuples-only \
    --no-align \
    --command "SELECT value FROM public.ict_recovery_probe"
)"
test "$restored_marker" = "synthetic-recovery-marker"
printf 'PostgreSQL backup and isolated restore drill passed (%s migrations; PostGIS %s).\n' \
  "$restored_migrations" "$restored_postgis"
