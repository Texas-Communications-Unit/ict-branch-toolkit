from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "reconcile-actions.py"
spec = importlib.util.spec_from_file_location("reconcile_actions", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def run(
    run_id: int,
    *,
    workflow_id: int = 1,
    path: str = ".github/workflows/security.yml",
    name: str = "Security",
    branch: str = "main",
    status: str = "completed",
    conclusion: str | None = "success",
    created_at: str = "2026-09-08T12:00:00Z",
    attempt: int = 1,
    sha: str = "abc123",
):
    return {
        "id": run_id,
        "workflow_id": workflow_id,
        "path": path,
        "name": name,
        "head_branch": branch,
        "head_sha": sha,
        "status": status,
        "conclusion": conclusion,
        "created_at": created_at,
        "run_attempt": attempt,
    }


def test_superseded_waiting_run_is_cancelled():
    older = run(
        10,
        workflow_id=2,
        path=".github/workflows/deploy.yml",
        name="Deploy to Server",
        status="waiting",
        conclusion=None,
        created_at="2026-09-08T12:00:00Z",
    )
    newer = run(
        11,
        workflow_id=2,
        path=".github/workflows/deploy.yml",
        name="Deploy to Server",
        status="pending",
        conclusion=None,
        created_at="2026-09-08T12:05:00Z",
    )

    actions = module.plan_superseded_cancellations([older, newer], current_run_id=999)

    assert [action.run_id for action in actions] == [10]


def test_in_progress_run_is_never_cancelled():
    older = run(
        10,
        workflow_id=2,
        status="in_progress",
        conclusion=None,
        created_at="2026-09-08T12:00:00Z",
    )
    newer = run(
        11,
        workflow_id=2,
        status="queued",
        conclusion=None,
        created_at="2026-09-08T12:05:00Z",
    )

    actions = module.plan_superseded_cancellations([older, newer], current_run_id=999)

    assert actions == []


def test_latest_allowlisted_failure_is_retry_candidate():
    failed = run(20, conclusion="failure")

    candidates = module.plan_retry_candidates([failed], current_run_id=999)

    assert [action.run_id for action, _ in candidates] == [20]


def test_old_failure_is_not_retried_when_newer_run_exists():
    failed = run(20, conclusion="failure", created_at="2026-09-08T12:00:00Z")
    newer = run(21, status="queued", conclusion=None, created_at="2026-09-08T12:05:00Z")

    candidates = module.plan_retry_candidates([failed, newer], current_run_id=999)

    assert candidates == []


def test_operational_workflow_failure_is_not_retried():
    failed = run(
        30,
        workflow_id=3,
        path=".github/workflows/deploy.yml",
        name="Deploy to Server",
        conclusion="failure",
    )

    candidates = module.plan_retry_candidates([failed], current_run_id=999)

    assert candidates == []


def test_second_attempt_is_not_retried_again():
    failed = run(40, conclusion="timed_out", attempt=2)

    candidates = module.plan_retry_candidates([failed], current_run_id=999)

    assert candidates == []


def test_reconciler_never_cancels_itself():
    self_run = run(
        50,
        workflow_id=4,
        path=module.SELF_WORKFLOW_PATH,
        name="Actions Reconciler",
        status="queued",
        conclusion=None,
    )
    newer = run(
        51,
        workflow_id=4,
        path=module.SELF_WORKFLOW_PATH,
        name="Actions Reconciler",
        status="queued",
        conclusion=None,
        created_at="2026-09-08T12:05:00Z",
    )

    actions = module.plan_superseded_cancellations([self_run, newer], current_run_id=999)

    assert actions == []
