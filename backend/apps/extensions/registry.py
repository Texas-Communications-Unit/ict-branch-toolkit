from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

from django.core.exceptions import ImproperlyConfigured

SUPPORTED_CONTRACT_VERSIONS = ("1.0",)

SYNTHETIC_EXTENSION_KEY = "synthetic-readiness-summary"
SYNTHETIC_EXTENSION_VERSION = "1.0.0"

SYNTHETIC_MANIFEST: dict[str, Any] = {
    "key": SYNTHETIC_EXTENSION_KEY,
    "name": "Synthetic readiness summary",
    "description": (
        "A non-operational example that validates the governed tool and report contract."
    ),
    "version": SYNTHETIC_EXTENSION_VERSION,
    "contract_version": "1.0",
    "provider": "ICT Branch Toolkit built-in synthetic example",
    "capabilities": [
        {
            "id": "readiness-check",
            "name": "Synthetic readiness check",
            "kind": "tool",
            "required_permission": "extension.run",
            "scope": "incident_revision",
            "inputs": {
                "source_revision": "approved_ics205",
                "minimum_assignment_count": {"type": "integer", "minimum": 1, "maximum": 1000},
            },
            "outputs": {
                "schema": "synthetic-readiness-tool-v1",
                "classification": "decision_support",
            },
            "validation": "Exact contract and an approved same-incident ICS-205 revision required.",
            "audit": "Actor, extension, capability, source revision, and digests are retained.",
            "export": {"formats": ["json"], "deterministic": True},
        },
        {
            "id": "readiness-report",
            "name": "Synthetic readiness report",
            "kind": "report",
            "required_permission": "extension.run",
            "scope": "incident_revision",
            "inputs": {
                "source_revision": "approved_ics205",
                "minimum_assignment_count": {"type": "integer", "minimum": 1, "maximum": 1000},
            },
            "outputs": {
                "schema": "synthetic-readiness-report-v1",
                "classification": "decision_support",
            },
            "validation": "Exact contract and an approved same-incident ICS-205 revision required.",
            "audit": "Actor, extension, capability, source revision, and digests are retained.",
            "export": {"formats": ["json"], "deterministic": True},
        },
    ],
    "source_records": [
        "Approved ICS-205 revision identifier, revision number, and assignment metadata/counts."
    ],
    "approval_requirements": (
        "This synthetic contract example is never an approval and produces no official form."
    ),
    "sensitivity": "internal_incident_metadata",
    "retention": "Retain with the incident; no automatic purge.",
    "failure_isolation": (
        "Runs execute only through the extension endpoint; failure cannot change source records."
    ),
    "accessibility": (
        "Results provide structured labels, text status, and a deterministic JSON alternative."
    ),
    "official_output": False,
}


def _summary_context(source_revision, parameters: dict[str, Any]) -> dict[str, Any]:
    assignments = list(
        source_revision.assignments.order_by("position", "id").values(
            "function",
            "operating_classification",
            "rx_frequency_hz",
            "tx_frequency_hz",
        )
    )
    minimum = parameters["minimum_assignment_count"]
    function_counts: dict[str, int] = {}
    missing_frequency_count = 0
    for assignment in assignments:
        function_name = assignment["function"].strip() or "Unspecified"
        function_counts[function_name] = function_counts.get(function_name, 0) + 1
        if assignment["operating_classification"] == "not_determined":
            missing_frequency_count += 1
    return {
        "assignment_count": len(assignments),
        "minimum_assignment_count": minimum,
        "missing_frequency_count": missing_frequency_count,
        "function_counts": [
            {"function": name, "count": count}
            for name, count in sorted(function_counts.items(), key=lambda item: item[0].casefold())
        ],
        "readiness_state": (
            "ready" if len(assignments) >= minimum and missing_frequency_count == 0 else "attention"
        ),
    }


def synthetic_readiness_tool(source_revision, parameters: dict[str, Any]) -> dict[str, Any]:
    summary = _summary_context(source_revision, parameters)
    return {
        "schema_version": "synthetic-readiness-tool-v1",
        **summary,
        "interpretation": (
            "Synthetic contract validation only. This result is not an operational approval."
        ),
    }


def synthetic_readiness_report(source_revision, parameters: dict[str, Any]) -> dict[str, Any]:
    summary = _summary_context(source_revision, parameters)
    return {
        "schema_version": "synthetic-readiness-report-v1",
        "title": "Synthetic ICS-205 readiness summary",
        "summary": {key: value for key, value in summary.items() if key != "function_counts"},
        "columns": ["Function", "Assignment count"],
        "rows": [[item["function"], item["count"]] for item in summary["function_counts"]],
        "interpretation": (
            "Synthetic contract validation only. This report is not an ICS form or approval."
        ),
    }


MANIFESTS = {SYNTHETIC_EXTENSION_KEY: SYNTHETIC_MANIFEST}
HANDLERS: dict[tuple[str, str], Callable[..., dict[str, Any]]] = {
    (SYNTHETIC_EXTENSION_KEY, "readiness-check"): synthetic_readiness_tool,
    (SYNTHETIC_EXTENSION_KEY, "readiness-report"): synthetic_readiness_report,
}


def validate_manifest(manifest: dict[str, Any]) -> None:
    required = {
        "key",
        "name",
        "description",
        "version",
        "contract_version",
        "provider",
        "capabilities",
        "source_records",
        "approval_requirements",
        "sensitivity",
        "retention",
        "failure_isolation",
        "accessibility",
        "official_output",
    }
    missing = sorted(required - set(manifest))
    if missing:
        raise ImproperlyConfigured(f"Extension manifest is missing: {', '.join(missing)}.")
    if manifest["contract_version"] not in SUPPORTED_CONTRACT_VERSIONS:
        raise ImproperlyConfigured(
            f"Extension contract {manifest['contract_version']} is not supported."
        )
    if manifest["official_output"] is not False:
        raise ImproperlyConfigured("Built-in example extensions cannot declare official output.")
    capabilities = manifest["capabilities"]
    if not isinstance(capabilities, list) or not capabilities:
        raise ImproperlyConfigured("Extension manifest must declare at least one capability.")
    capability_ids = set()
    for capability in capabilities:
        capability_id = capability.get("id")
        if (
            not capability_id
            or capability_id in capability_ids
            or capability.get("kind") not in {"tool", "report"}
            or capability.get("required_permission") != "extension.run"
            or capability.get("scope") != "incident_revision"
            or capability.get("outputs", {}).get("classification")
            not in {
                "draft",
                "decision_support",
                "official",
            }
        ):
            raise ImproperlyConfigured("Extension manifest contains an invalid capability.")
        capability_ids.add(capability_id)
        if (
            not manifest["official_output"]
            and capability.get("outputs", {}).get("classification") == "official"
        ):
            raise ImproperlyConfigured(
                "A non-official extension cannot declare official capability output."
            )
        if (manifest["key"], capability_id) not in HANDLERS:
            raise ImproperlyConfigured(
                f"Extension capability {manifest['key']}:{capability_id} has no built-in handler."
            )


def get_manifest(extension_key: str) -> dict[str, Any]:
    try:
        manifest = MANIFESTS[extension_key]
    except KeyError as exc:
        raise KeyError("The requested extension is not in the server registry.") from exc
    validate_manifest(manifest)
    return deepcopy(manifest)


def get_capability(extension_key: str, capability_id: str) -> tuple[dict[str, Any], Callable]:
    manifest = get_manifest(extension_key)
    capability = next(
        (item for item in manifest["capabilities"] if item["id"] == capability_id),
        None,
    )
    if not capability:
        raise KeyError("The requested capability is not declared by this extension.")
    return deepcopy(capability), HANDLERS[(extension_key, capability_id)]
