#!/usr/bin/env python3
"""Focused tests for retained capacity-report validation."""

from __future__ import annotations

import importlib.util
import io
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from types import ModuleType


def load_validator() -> ModuleType:
    script_path = Path(__file__).with_name("validate-capacity-report.py")
    spec = importlib.util.spec_from_file_location(
        "validate_capacity_report", script_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALIDATOR = load_validator()


def valid_events() -> list[dict[str, object]]:
    integrity = {
        "audit_chain_valid": True,
        "cross_incident_isolation_valid": True,
        "independent_saves_valid": True,
        "same_field_conflict_valid": True,
        "restricted_field_leakage_detected": False,
    }
    return [
        {
            "event": "capacity_probe_started",
            "run_id": "synthetic-run",
            "levels": [5],
            "synthetic_only": True,
            "production_capacity_claim": False,
        },
        {
            "event": "capacity_level_completed",
            "run_id": "synthetic-run",
            "concurrent_users": 5,
            "latency_ms": {"p50": 10, "p95": 20, "p99": 25, "maximum": 30},
            "integrity": integrity,
        },
        {
            "event": "capacity_probe_finished",
            "run_id": "synthetic-run",
            "completed_levels": [5],
            "highest_characterized_level": 5,
            "fixtures_retained_hidden": True,
            "tokens_revoked": True,
            "production_capacity_claim": False,
        },
    ]


class CapacityReportValidationTests(unittest.TestCase):
    def test_valid_report_is_accepted(self) -> None:
        summary = VALIDATOR.validate(valid_events())
        self.assertEqual(summary["highest_characterized_level"], 5)
        self.assertTrue(summary["synthetic_only"])
        self.assertFalse(summary["production_capacity_claim"])

    def test_restricted_field_leakage_is_rejected(self) -> None:
        events = valid_events()
        events[1]["integrity"]["restricted_field_leakage_detected"] = True
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            VALIDATOR.validate(events)

    def test_missing_p99_is_rejected(self) -> None:
        events = valid_events()
        del events[1]["latency_ms"]["p99"]
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            VALIDATOR.validate(events)

    def test_short_ramp_requires_safe_stop_evidence(self) -> None:
        events = valid_events()
        events[0]["levels"] = [5, 10]
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            VALIDATOR.validate(events)


if __name__ == "__main__":
    unittest.main()
