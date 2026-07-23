#!/usr/bin/env bash
set -euo pipefail

workflow_dir=".github/workflows"
workflow_count=0

while IFS= read -r -d '' workflow; do
  workflow_count=$((workflow_count + 1))
  if ! grep -q 'FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"' "$workflow"; then
    echo "$workflow does not enforce the Node.js 24 action runtime." >&2
    exit 1
  fi
done < <(find "$workflow_dir" -maxdepth 1 -type f \
  \( -name '*.yml' -o -name '*.yaml' \) -print0)

if [[ "$workflow_count" -eq 0 ]]; then
  echo "No GitHub Actions workflows were found." >&2
  exit 1
fi

if grep -REn \
  'node-version: *"?20|actions/github-script@v[1-7]|pnpm/action-setup@v[1-5]' \
  "$workflow_dir"; then
  echo "A deprecated Node.js 20 workflow configuration was found." >&2
  exit 1
fi

printf 'Verified Node.js 24 enforcement in %s workflow(s).\n' "$workflow_count"
