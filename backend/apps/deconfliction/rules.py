from __future__ import annotations

import math
from itertools import combinations
from typing import Any

RULE_SET_ID = "rf-deconfliction"
RULE_SET_VERSION = "rf-deconfliction-v1-provisional"
ADJACENT_THRESHOLD_HZ = 12_500
DISCLAIMER = (
    "Decision support only—not a coordination decision, spectrum authorization, "
    "propagation study, or substitute for qualified practitioner review."
)
RULE_DEFINITIONS = [
    {
        "id": "RF-001",
        "name": "Co-channel overlap",
        "severity": "critical",
        "summary": (
            "Operating frequencies match and approved operating or coordination areas overlap."
        ),
    },
    {
        "id": "RF-002",
        "name": "Adjacent-channel overlap",
        "severity": "warning",
        "summary": (
            "Operating frequencies are within the provisional adjacent-channel "
            "threshold and approved areas overlap."
        ),
    },
    {
        "id": "RF-003",
        "name": "Reversed repeater pair",
        "severity": "critical",
        "summary": "Receive and transmit frequencies are reversed between assignments.",
    },
    {
        "id": "RF-004",
        "name": "Duplicate frequency under different names",
        "severity": "warning",
        "summary": "Different channel names use the same receive/transmit frequency pair.",
    },
    {
        "id": "RF-005",
        "name": "Missing technical values",
        "severity": "caution",
        "summary": "An assignment omits a receive or transmit frequency.",
    },
    {
        "id": "RF-006",
        "name": "Active resource omitted",
        "severity": "warning",
        "summary": "A selected active resource is absent from the approved ICS-205.",
    },
    {
        "id": "RF-007",
        "name": "Missing operating or coordination area",
        "severity": "caution",
        "summary": "An assignment has no approved operating or coordination ring snapshot.",
    },
]
RULE_BY_ID = {rule["id"]: rule for rule in RULE_DEFINITIONS}


def rule_set_status(*, approved: bool) -> dict[str, Any]:
    return {
        "rule_set_id": RULE_SET_ID,
        "rule_set_version": RULE_SET_VERSION,
        "approved_for_operational_use": approved,
        "adjacent_channel_threshold_hz": ADJACENT_THRESHOLD_HZ,
        "rules": RULE_DEFINITIONS,
        "squelch_rule": (
            "CTCSS, DCS, NAC, or other squelch differences never suppress a frequency warning."
        ),
        "disclaimer": DISCLAIMER,
    }


def _distance_m(first: dict[str, Any], second: dict[str, Any]) -> float:
    earth_radius_m = 6_371_008.8
    first_latitude = math.radians(float(first["latitude"]))
    second_latitude = math.radians(float(second["latitude"]))
    delta_latitude = second_latitude - first_latitude
    delta_longitude = math.radians(float(second["longitude"]) - float(first["longitude"]))
    haversine = (
        math.sin(delta_latitude / 2) ** 2
        + math.cos(first_latitude) * math.cos(second_latitude) * math.sin(delta_longitude / 2) ** 2
    )
    return (
        earth_radius_m
        * 2
        * math.atan2(
            math.sqrt(haversine),
            math.sqrt(1 - haversine),
        )
    )


def _overlap_evidence(
    first: dict[str, Any],
    second: dict[str, Any],
) -> dict[str, Any] | None:
    for first_area in first["areas"]:
        for second_area in second["areas"]:
            center_distance_m = round(_distance_m(first_area, second_area), 3)
            supported_distance_m = first_area["radius_m"] + second_area["radius_m"]
            if center_distance_m <= supported_distance_m:
                return {
                    "first_area": first_area,
                    "second_area": second_area,
                    "center_distance_m": center_distance_m,
                    "combined_radius_m": supported_distance_m,
                    "overlap_test": "center_distance_m <= combined_radius_m",
                }
    return None


def _compared_input(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item["id"],
        "name": item["channel_name"],
        "rx_frequency_hz": item["rx_frequency_hz"],
        "tx_frequency_hz": item["tx_frequency_hz"],
        "rx_squelch": item["rx_squelch"],
        "tx_squelch": item["tx_squelch"],
    }


def _warning(
    rule_id: str,
    *,
    compared_inputs: list[dict[str, Any]],
    evidence: dict[str, Any],
    assumptions: list[str],
    explanation: str,
) -> dict[str, Any]:
    rule = RULE_BY_ID[rule_id]
    return {
        "rule_id": rule_id,
        "rule_name": rule["name"],
        "rule_set_version": RULE_SET_VERSION,
        "severity": rule["severity"],
        "compared_inputs": compared_inputs,
        "evidence": evidence,
        "assumptions": assumptions,
        "explanation": explanation,
        "disclaimer": DISCLAIMER,
    }


def evaluate(
    assignments: list[dict[str, Any]],
    active_resources: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    squelch_assumption = (
        "Squelch values are evidence only and do not suppress RF conflict warnings."
    )

    for assignment in assignments:
        missing = [
            field for field in ("rx_frequency_hz", "tx_frequency_hz") if assignment[field] is None
        ]
        if missing:
            warnings.append(
                _warning(
                    "RF-005",
                    compared_inputs=[_compared_input(assignment)],
                    evidence={"missing_fields": missing},
                    assumptions=[
                        "A missing value may be deliberate but requires practitioner review."
                    ],
                    explanation=(
                        f"{assignment['channel_name']} omits {', '.join(missing)}; "
                        "the engine will not invent a simplex or repeater value."
                    ),
                )
            )
        if not assignment["areas"]:
            warnings.append(
                _warning(
                    "RF-007",
                    compared_inputs=[_compared_input(assignment)],
                    evidence={"approved_area_count": 0},
                    assumptions=["Only frozen operational or coordination rings are considered."],
                    explanation=(
                        f"{assignment['channel_name']} has no approved operating or "
                        "coordination area, so overlap rules cannot evaluate it."
                    ),
                )
            )

    for first, second in combinations(assignments, 2):
        first_tx = first["tx_frequency_hz"]
        second_tx = second["tx_frequency_hz"]
        overlap = _overlap_evidence(first, second)
        compared = [_compared_input(first), _compared_input(second)]
        if first_tx is not None and second_tx is not None and overlap:
            separation_hz = abs(first_tx - second_tx)
            evidence = {
                "first_operating_frequency_hz": first_tx,
                "second_operating_frequency_hz": second_tx,
                "separation_hz": separation_hz,
                "area_overlap": overlap,
                "squelch_values_differ": (first["tx_squelch"] != second["tx_squelch"]),
            }
            if separation_hz == 0:
                warnings.append(
                    _warning(
                        "RF-001",
                        compared_inputs=compared,
                        evidence=evidence,
                        assumptions=[squelch_assumption],
                        explanation=(
                            f"{first['channel_name']} and {second['channel_name']} "
                            "use the same operating frequency inside overlapping approved areas."
                        ),
                    )
                )
            elif separation_hz <= ADJACENT_THRESHOLD_HZ:
                warnings.append(
                    _warning(
                        "RF-002",
                        compared_inputs=compared,
                        evidence={
                            **evidence,
                            "inclusive_threshold_hz": ADJACENT_THRESHOLD_HZ,
                        },
                        assumptions=[
                            squelch_assumption,
                            (
                                "The provisional center-frequency threshold is inclusive "
                                "and does not model receiver selectivity or emission masks."
                            ),
                        ],
                        explanation=(
                            f"{first['channel_name']} and {second['channel_name']} "
                            f"are {separation_hz} Hz apart inside overlapping approved areas."
                        ),
                    )
                )

        if (
            first["rx_frequency_hz"] is not None
            and first["tx_frequency_hz"] is not None
            and second["rx_frequency_hz"] is not None
            and second["tx_frequency_hz"] is not None
            and first["rx_frequency_hz"] == second["tx_frequency_hz"]
            and first["tx_frequency_hz"] == second["rx_frequency_hz"]
            and first["rx_frequency_hz"] != first["tx_frequency_hz"]
        ):
            warnings.append(
                _warning(
                    "RF-003",
                    compared_inputs=compared,
                    evidence={
                        "first_pair": [
                            first["rx_frequency_hz"],
                            first["tx_frequency_hz"],
                        ],
                        "second_pair": [
                            second["rx_frequency_hz"],
                            second["tx_frequency_hz"],
                        ],
                    },
                    assumptions=[squelch_assumption],
                    explanation=(
                        f"{first['channel_name']} and {second['channel_name']} "
                        "have reversed receive/transmit frequency pairs."
                    ),
                )
            )

        if (
            first["channel_name"].casefold() != second["channel_name"].casefold()
            and first["rx_frequency_hz"] == second["rx_frequency_hz"]
            and first["tx_frequency_hz"] == second["tx_frequency_hz"]
            and first["rx_frequency_hz"] is not None
        ):
            warnings.append(
                _warning(
                    "RF-004",
                    compared_inputs=compared,
                    evidence={
                        "shared_rx_frequency_hz": first["rx_frequency_hz"],
                        "shared_tx_frequency_hz": first["tx_frequency_hz"],
                    },
                    assumptions=[squelch_assumption],
                    explanation=(
                        f"{first['channel_name']} and {second['channel_name']} use "
                        "the same frequency pair under different names."
                    ),
                )
            )

    assigned_resource_ids = {
        assignment["resource_id"]
        for assignment in assignments
        if assignment["resource_id"] is not None
    }
    for resource in active_resources:
        if resource["id"] not in assigned_resource_ids:
            warnings.append(
                _warning(
                    "RF-006",
                    compared_inputs=[
                        {
                            "id": resource["id"],
                            "name": resource["name"],
                            "rx_frequency_hz": resource["rx_frequency_hz"],
                            "tx_frequency_hz": resource["tx_frequency_hz"],
                            "rx_squelch": resource["rx_squelch"],
                            "tx_squelch": resource["tx_squelch"],
                        }
                    ],
                    evidence={
                        "resource_identifier": resource["identifier"],
                        "resource_release": resource["release"],
                        "resource_content_sha256": resource["content_sha256"],
                        "approved_revision_assignment_count": len(assignments),
                    },
                    assumptions=[
                        "Only resources explicitly selected for this analysis are checked."
                    ],
                    explanation=(
                        f"Selected active resource {resource['name']} is not present "
                        "in the approved ICS-205 revision."
                    ),
                )
            )

    return sorted(
        warnings,
        key=lambda warning: (
            warning["rule_id"],
            [item["id"] for item in warning["compared_inputs"]],
        ),
    )
