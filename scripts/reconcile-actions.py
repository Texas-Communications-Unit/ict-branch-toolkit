#!/usr/bin/env python3
"""Conservatively reconcile recent GitHub Actions runs.

The reconciler cancels only superseded runs that have not started and retries
only explicitly allowlisted validation workflows. It never approves protected
environments, cancels in-progress work, deploys, merges, or deletes run history.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

API_VERSION = "2022-11-28"
ACTIVE_CANCELABLE_STATUSES = {"queued", "requested", "waiting", "pending"}
RETRYABLE_CONCLUSIONS = {"failure", "timed_out"}
RETRYABLE_WORKFLOW_PATHS = {
    ".github/workflows/security.yml",
    ".github/workflows/phase-2-release-candidate-evaluation.yml",
}
SELF_WORKFLOW_PATH = ".github/workflows/actions-reconciler.yml"
MAX_PAGES = 3
PER_PAGE = 100
LOOKBACK_HOURS = 48
MAX_AUTOMATIC_ATTEMPTS = 2


@dataclass(frozen=True)
class PlannedAction:
    kind: str
    run_id: int
    workflow: str
    branch: str | None
    reason: str


class GitHubAPI:
    def __init__(self, repository: str, token: str) -> None:
        self.repository = repository
        self.token = token
        self.base = f"https://api.github.com/repos/{repository}"

    def request(self, method: str, path: str) -> Any:
        request = urllib.request.Request(
            f"{self.base}{path}",
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": API_VERSION,
                "User-Agent": "ict-toolkit-actions-reconciler",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                if response.status == 204:
                    return None
                payload = response.read()
                return json.loads(payload) if payload else None
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"GitHub API {method} {path} failed with {exc.code}: {body}"
            ) from exc

    def recent_runs(self, cutoff: datetime) -> list[dict[str, Any]]:
        runs: list[dict[str, Any]] = []
        for page in range(1, MAX_PAGES + 1):
            payload = self.request(
                "GET", f"/actions/runs?per_page={PER_PAGE}&page={page}"
            )
            page_runs = payload.get("workflow_runs", [])
            if not page_runs:
                break
            runs.extend(page_runs)
            oldest = min(parse_time(run["created_at"]) for run in page_runs)
            if oldest < cutoff:
                break
        return [run for run in runs if parse_time(run["created_at"]) >= cutoff]

    def branch_tip(self, branch: str) -> str | None:
        encoded = urllib.parse.quote(branch, safe="")
        try:
            payload = self.request("GET", f"/branches/{encoded}")
        except RuntimeError as exc:
            if "failed with 404" in str(exc):
                return None
            raise
        return payload["commit"]["sha"]

    def cancel_run(self, run_id: int) -> None:
        self.request("POST", f"/actions/runs/{run_id}/cancel")

    def rerun_failed_jobs(self, run_id: int) -> None:
        self.request("POST", f"/actions/runs/{run_id}/rerun-failed-jobs")


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def run_key(run: dict[str, Any]) -> tuple[int, str | None]:
    return int(run["workflow_id"]), run.get("head_branch")


def latest_runs_by_key(runs: list[dict[str, Any]]) -> dict[tuple[int, str | None], dict[str, Any]]:
    latest: dict[tuple[int, str | None], dict[str, Any]] = {}
    for run in sorted(runs, key=lambda item: parse_time(item["created_at"]), reverse=True):
        latest.setdefault(run_key(run), run)
    return latest


def plan_superseded_cancellations(
    runs: list[dict[str, Any]], current_run_id: int
) -> list[PlannedAction]:
    latest = latest_runs_by_key(runs)
    actions: list[PlannedAction] = []
    for run in runs:
        if int(run["id"]) == current_run_id or run.get("path") == SELF_WORKFLOW_PATH:
            continue
        if run.get("status") not in ACTIVE_CANCELABLE_STATUSES:
            continue
        newest = latest.get(run_key(run))
        if not newest or int(newest["id"]) == int(run["id"]):
            continue
        actions.append(
            PlannedAction(
                kind="cancel",
                run_id=int(run["id"]),
                workflow=run.get("name", run.get("path", "unknown")),
                branch=run.get("head_branch"),
                reason=f"superseded by newer run {newest['id']} for the same workflow/branch",
            )
        )
    return actions


def plan_retry_candidates(
    runs: list[dict[str, Any]], current_run_id: int
) -> list[tuple[PlannedAction, dict[str, Any]]]:
    latest = latest_runs_by_key(runs)
    candidates: list[tuple[PlannedAction, dict[str, Any]]] = []
    for run in runs:
        if int(run["id"]) == current_run_id or run.get("path") == SELF_WORKFLOW_PATH:
            continue
        if run.get("status") != "completed":
            continue
        if run.get("conclusion") not in RETRYABLE_CONCLUSIONS:
            continue
        if run.get("path") not in RETRYABLE_WORKFLOW_PATHS:
            continue
        if int(run.get("run_attempt", 1)) >= MAX_AUTOMATIC_ATTEMPTS:
            continue
        newest = latest.get(run_key(run))
        if not newest or int(newest["id"]) != int(run["id"]):
            continue
        branch = run.get("head_branch")
        if not branch:
            continue
        candidates.append(
            (
                PlannedAction(
                    kind="retry",
                    run_id=int(run["id"]),
                    workflow=run.get("name", run.get("path", "unknown")),
                    branch=branch,
                    reason="latest failed/timed-out allowlisted validation run",
                ),
                run,
            )
        )
    return candidates


def append_summary(lines: list[str]) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    else:
        print("\n".join(lines))


def main() -> int:
    repository = os.environ.get("GITHUB_REPOSITORY")
    token = os.environ.get("GITHUB_TOKEN")
    current_run_id_text = os.environ.get("GITHUB_RUN_ID")
    dry_run = os.environ.get("RECONCILER_DRY_RUN", "false").lower() == "true"
    if not repository or not token or not current_run_id_text:
        print("GITHUB_REPOSITORY, GITHUB_TOKEN, and GITHUB_RUN_ID are required.", file=sys.stderr)
        return 2

    current_run_id = int(current_run_id_text)
    api = GitHubAPI(repository, token)
    cutoff = datetime.now(UTC) - timedelta(hours=LOOKBACK_HOURS)
    runs = api.recent_runs(cutoff)
    cancellations = plan_superseded_cancellations(runs, current_run_id)
    retry_candidates = plan_retry_candidates(runs, current_run_id)

    performed: list[PlannedAction] = []
    skipped: list[str] = []
    errors: list[str] = []

    for action in cancellations:
        if dry_run:
            skipped.append(f"DRY RUN: would cancel {action.run_id} ({action.reason})")
            continue
        try:
            api.cancel_run(action.run_id)
            performed.append(action)
        except RuntimeError as exc:
            errors.append(str(exc))

    tip_cache: dict[str, str | None] = {}
    for action, run in retry_candidates:
        branch = action.branch
        assert branch is not None
        if branch not in tip_cache:
            try:
                tip_cache[branch] = api.branch_tip(branch)
            except RuntimeError as exc:
                errors.append(str(exc))
                continue
        tip = tip_cache[branch]
        if tip is None:
            skipped.append(
                f"run {action.run_id}: branch {branch!r} no longer exists in this repository"
            )
            continue
        if tip != run.get("head_sha"):
            skipped.append(
                f"run {action.run_id}: branch tip {tip[:12]} supersedes failed SHA {run.get('head_sha', '')[:12]}"
            )
            continue
        if dry_run:
            skipped.append(f"DRY RUN: would retry failed jobs for {action.run_id}")
            continue
        try:
            api.rerun_failed_jobs(action.run_id)
            performed.append(action)
        except RuntimeError as exc:
            errors.append(str(exc))

    lines = [
        "## Actions reconciler",
        "",
        f"- Evaluated recent runs: **{len(runs)}**",
        f"- Lookback: **{LOOKBACK_HOURS} hours**",
        f"- Dry run: **{'yes' if dry_run else 'no'}**",
        f"- Actions performed: **{len(performed)}**",
        f"- Skipped/observed: **{len(skipped)}**",
        f"- Errors: **{len(errors)}**",
        "",
    ]
    if performed:
        lines.extend(["### Performed", ""])
        for action in performed:
            lines.append(
                f"- `{action.kind}` run **{action.run_id}** — {action.workflow} — {action.reason}"
            )
        lines.append("")
    if skipped:
        lines.extend(["### Skipped", ""])
        lines.extend(f"- {item}" for item in skipped)
        lines.append("")
    if errors:
        lines.extend(["### Errors", ""])
        lines.extend(f"- {item}" for item in errors)
        lines.append("")
    if not performed and not skipped and not errors:
        lines.append("No reconciliation action was needed.")

    append_summary(lines)
    if errors:
        print("Reconciliation completed with API errors; see job summary.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
