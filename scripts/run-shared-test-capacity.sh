#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 || ! "$1" =~ ^[0-9a-f]{40}$ || ! "$2" =~ ^[0-9]+$ || ! "$3" =~ ^[0-9]+$ ]]; then
  echo "Usage: run-shared-test-capacity.sh <40-character-main-commit> <run-id> <attempt>" >&2
  exit 2
fi

expected_sha="$1"
github_run_id="$2"
github_run_attempt="$3"
app_dir="$HOME/apps/ict-branch-toolkit"
env_file="$HOME/.config/ict-branch-toolkit/deployment.env"
report_dir="$HOME/reports/ict-branch-toolkit/capacity"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
report_validator="$script_dir/validate-capacity-report.py"
report_name="capacity-${expected_sha:0:12}-github-${github_run_id}-${github_run_attempt}.jsonl"
report_file="$report_dir/$report_name"

if [[ ! -f "$env_file" ]]; then
  echo "Refusing capacity run because the protected environment file is missing." >&2
  exit 1
fi
if [[ ! -f "$report_validator" ]]; then
  echo "Refusing capacity run because the report validator is missing." >&2
  exit 1
fi

cd "$app_dir"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Refusing capacity run because the server checkout has uncommitted changes." >&2
  exit 1
fi

git fetch --prune origin main
remote_sha="$(git rev-parse origin/main)"
deployed_sha="$(git rev-parse HEAD)"
if [[ "$remote_sha" != "$expected_sha" ]]; then
  echo "Refusing capacity run because the requested commit is not current origin/main." >&2
  exit 1
fi
if [[ "$deployed_sha" != "$expected_sha" ]]; then
  echo "Refusing capacity run because shared test is not deployed at the requested commit." >&2
  exit 1
fi

compose=(docker compose --env-file "$env_file" -f compose.production.yaml)
"${compose[@]}" config --quiet

for service in db backend frontend; do
  container_id="$("${compose[@]}" ps -q "$service")"
  if [[ -z "$container_id" ]]; then
    echo "Refusing capacity run because the $service container is missing." >&2
    exit 1
  fi
  state="$(docker inspect --format '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}' "$container_id")"
  if [[ "$state" != "running healthy" ]]; then
    echo "Refusing capacity run because the $service container is not running and healthy." >&2
    exit 1
  fi
done

"${compose[@]}" exec -T backend python manage.py migrate --check
"${compose[@]}" exec -T backend python manage.py shell -c \
  'from django.conf import settings; assert settings.ICT_EXTERNAL_SSO_ENABLED is False'

revoke_synthetic_tokens() {
  set +e
  "${compose[@]}" exec -T backend python manage.py shell -c \
    'from rest_framework.authtoken.models import Token; Token.objects.filter(user__username__startswith="synthetic_capacity_", user__local_contingency_account__is_synthetic_hidden=True).delete()' \
    >/dev/null 2>&1
  return 0
}
trap revoke_synthetic_tokens EXIT

umask 077
install -d -m 700 "$report_dir"
if [[ -e "$report_file" ]]; then
  echo "Refusing capacity run because the run-specific report already exists." >&2
  exit 1
fi

"${compose[@]}" exec -T backend \
  python manage.py probe_collaboration_capacity \
  --base-url http://127.0.0.1:8000 \
  --host-header backend \
  --levels 5,10,25,50,100 \
  --max-error-rate 0.02 \
  --maximum-cpu-percent 90 \
  --minimum-memory-available-percent 10 |
  tee "$report_file"

python3 "$report_validator" "$report_file"
(
  cd "$report_dir"
  sha256sum "$report_name" > "$report_name.sha256"
)
chmod 600 "$report_file" "$report_file.sha256"

printf 'Retained validated synthetic capacity report: %s\n' "$report_file"
