#!/usr/bin/env python3
"""Focused tests for the deployment environment validator."""

from __future__ import annotations

import importlib.util
import io
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from types import ModuleType


def load_validator() -> ModuleType:
    script_path = Path(__file__).with_name("validate-compose-environment.py")
    spec = importlib.util.spec_from_file_location(
        "validate_compose_environment", script_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALIDATOR = load_validator()


def compose_configuration() -> dict[str, object]:
    environment = {
        setting_name: "{}" if expected_type is dict else "[]"
        for setting_name, (expected_type, _, _) in VALIDATOR.JSON_SETTINGS.items()
    }
    return {"services": {"backend": {"environment": environment}}}


class DeploymentEnvironmentValidationTests(unittest.TestCase):
    def test_valid_json_environment_is_accepted(self) -> None:
        VALIDATOR.validate(compose_configuration())

    def test_invalid_json_is_rejected_without_echoing_value(self) -> None:
        configuration = compose_configuration()
        malformed_value = "[rf-deconfliction-v2-reviewed]"
        configuration["services"]["backend"]["environment"][
            "ICT_APPROVED_DECONFLICTION_RULESETS"
        ] = malformed_value
        error = io.StringIO()

        with redirect_stderr(error), self.assertRaises(SystemExit):
            VALIDATOR.validate(configuration)

        self.assertIn(
            "ICT_APPROVED_DECONFLICTION_RULESETS does not contain valid JSON",
            error.getvalue(),
        )
        self.assertNotIn(malformed_value, error.getvalue())

    def test_wrong_json_type_is_rejected(self) -> None:
        configuration = compose_configuration()
        configuration["services"]["backend"]["environment"]["ICT_COVERAGE_PRESETS"] = (
            "[]"
        )

        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            VALIDATOR.validate(configuration)


if __name__ == "__main__":
    unittest.main()
