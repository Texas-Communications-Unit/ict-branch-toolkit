#!/usr/bin/env python3
"""Validate a retained synthetic collaboration-capacity JSON Lines report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

INTEGRITY_EXPECTATIONS = {
    "audit_chain_valid": True,
    "cross_incident_isolation_valid": True,
    "independent_saves_valid": True,
    "same_field_conflict_valid": True,
    "restricted_field_leakage_detected": False,
}


def fail(message: str) -> None:
    print(f"Capacity report validation failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_events(path: Path) -> list[dict[str, Any]]:
    events = []
    try:
        with path.open(encoding="utf-8") as report:
            for line_number, line in enumerate(report, start=1):
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    fail(f"line {line_number} is not valid JSON.")
                if not isinstance(event, dict):
                    fail(f"line {line_number} is not a JSON object.")
                events.append(event)
    except OSError:
        fail("the report could not be read.")
    if not events:
        fail("the report is empty.")
    return events


def exactly_one(events: list[dict[str, Any]], event_name: str) -> dict[str, Any]:
    matches = [event for event in events if event.get("event") == event_name]
    if len(matches) != 1:
        fail(f"expected exactly one {event_name} event.")
    return matches[0]


def validate(events: list[dict[str, Any]]) -> dict[str, Any]:
    started = exactly_one(events, "capacity_probe_started")
    finished = exactly_one(events, "capacity_probe_finished")
    levels = [
        event for event in events if event.get("event") == "capacity_level_completed"
    ]
    safely_stopped = [
        event
        for event in events
        if event.get("event") == "capacity_probe_stopped_safely"
    ]

    run_id = started.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        fail("the start event does not contain a run identifier.")
    if any(event.get("run_id") != run_id for event in events):
        fail("events do not share one run identifier.")
    if started.get("synthetic_only") is not True:
        fail("the report is not explicitly marked synthetic-only.")
    if any(event.get("production_capacity_claim") is True for event in events):
        fail("the report contains a production-capacity claim.")
    if not levels:
        fail("the report does not contain a completed capacity level.")

    requested_levels = started.get("levels")
    completed_levels = finished.get("completed_levels")
    measured_levels = [event.get("concurrent_users") for event in levels]
    if not isinstance(requested_levels, list) or not all(
        isinstance(level, int) for level in requested_levels
    ):
        fail("the requested levels are invalid.")
    if completed_levels != measured_levels:
        fail("the finished and measured levels do not match.")
    if finished.get("highest_characterized_level") != max(measured_levels):
        fail("the highest characterized level is inconsistent.")
    if measured_levels != requested_levels and len(safely_stopped) != 1:
        fail("an incomplete ramp is missing its safe-stop event.")

    for level in levels:
        latency = level.get("latency_ms")
        if not isinstance(latency, dict) or any(
            not isinstance(latency.get(percentile), (int, float))
            for percentile in ("p50", "p95", "p99", "maximum")
        ):
            fail("a completed level is missing required latency percentiles.")
        integrity = level.get("integrity")
        if not isinstance(integrity, dict):
            fail("a completed level is missing integrity evidence.")
        for field, expected in INTEGRITY_EXPECTATIONS.items():
            if integrity.get(field) is not expected:
                fail(f"a completed level failed {field}.")

    if finished.get("fixtures_retained_hidden") is not True:
        fail("hidden synthetic fixture retention is not confirmed.")
    if finished.get("tokens_revoked") is not True:
        fail("synthetic token revocation is not confirmed.")
    if finished.get("production_capacity_claim") is not False:
        fail("the final event does not disclaim a production-capacity claim.")

    return {
        "run_id": run_id,
        "completed_levels": completed_levels,
        "highest_characterized_level": max(measured_levels),
        "stopped_safely": bool(safely_stopped),
        "synthetic_only": True,
        "production_capacity_claim": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    summary = validate(load_events(args.report))
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
