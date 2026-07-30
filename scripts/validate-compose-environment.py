#!/usr/bin/env python3
"""Validate JSON-valued settings in an effective Docker Compose configuration."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from typing import Any

JSON_SETTINGS: dict[str, tuple[type, Callable[[Any], bool] | None, str]] = {
    "ICT_ROLE_POLICY_OVERRIDES": (dict, None, "a JSON object"),
    "ICT_EXTERNAL_ROLE_MAPPINGS": (dict, None, "a JSON object"),
    "ICT_RESTRICTED_FIELD_DEFAULT_VIEW_ROLES": (
        list,
        lambda value: all(isinstance(item, str) for item in value),
        "a JSON array of strings",
    ),
    "ICT_RESTRICTED_FIELD_DEFAULT_EDIT_ROLES": (
        list,
        lambda value: all(isinstance(item, str) for item in value),
        "a JSON array of strings",
    ),
    "ICT_APPROVED_REFERENCE_IMPORTS": (list, None, "a JSON array"),
    "ICT_APPROVED_ELEVATION_SOURCES": (list, None, "a JSON array"),
    "ICT_COVERAGE_PRESETS": (dict, None, "a JSON object"),
    "ICT_APPROVED_COVERAGE_CONFIGURATIONS": (list, None, "a JSON array"),
    "ICT_APPROVED_DIRECTIONAL_RULES": (
        list,
        lambda value: all(isinstance(item, str) for item in value),
        "a JSON array of strings",
    ),
    "ICT_APPROVED_CALIBRATION_METHODS": (
        list,
        lambda value: all(isinstance(item, str) for item in value),
        "a JSON array of strings",
    ),
    "ICT_APPROVED_PHASE2_VALIDATION_PROFILES": (
        list,
        lambda value: all(isinstance(item, str) for item in value),
        "a JSON array of strings",
    ),
    "ICT_APPROVED_DECONFLICTION_RULESETS": (
        list,
        lambda value: all(isinstance(item, str) for item in value),
        "a JSON array of strings",
    ),
    "ICT_APPROVED_TERRAIN_CONFIGURATIONS": (
        list,
        lambda value: all(isinstance(item, dict) for item in value),
        "a JSON array of objects",
    ),
}


def fail(message: str) -> None:
    print(f"Deployment environment validation failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def backend_environment(configuration: Any) -> dict[str, Any]:
    if not isinstance(configuration, dict):
        fail("Compose configuration must be a JSON object.")

    services = configuration.get("services")
    if not isinstance(services, dict):
        fail("Compose configuration does not contain a services object.")

    backend = services.get("backend")
    if not isinstance(backend, dict):
        fail("Compose configuration does not contain the backend service.")

    environment = backend.get("environment")
    if not isinstance(environment, dict):
        fail("The backend service environment must be an object.")
    return environment


def validate(configuration: Any) -> None:
    environment = backend_environment(configuration)
    errors: list[str] = []

    for setting_name, (
        expected_type,
        member_check,
        description,
    ) in JSON_SETTINGS.items():
        raw_value = environment.get(setting_name)
        if not isinstance(raw_value, str):
            errors.append(f"{setting_name} must resolve to {description}")
            continue
        try:
            parsed_value = json.loads(raw_value)
        except json.JSONDecodeError:
            errors.append(f"{setting_name} does not contain valid JSON")
            continue
        if not isinstance(parsed_value, expected_type) or (
            member_check is not None and not member_check(parsed_value)
        ):
            errors.append(f"{setting_name} must resolve to {description}")

    if errors:
        fail("; ".join(errors) + ".")


def main() -> None:
    try:
        configuration = json.load(sys.stdin)
    except json.JSONDecodeError:
        fail("Docker Compose did not produce valid JSON.")
    validate(configuration)
    print("Effective Compose JSON environment validated.")


if __name__ == "__main__":
    main()
