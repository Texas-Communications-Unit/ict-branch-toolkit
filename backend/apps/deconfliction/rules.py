from __future__ import annotations

import math
from itertools import combinations
from typing import Any

RULE_SET_ID = "rf-deconfliction"
RULE_SET_VERSION = "rf-deconfliction-v2-reviewed"
CLOSE_FREQUENCY_THRESHOLD_HZ = 12_500
DISCLAIMER = (
    "Decision support only. Results do not constitute frequency coordination, "
    "spectrum authorization, an interference determination, a propagation study, "
    "or operational approval. Qualified practitioners must review the results "
    "before operational use."
)
RULE_DEFINITIONS = [
    {
        "id": "RF-001",
        "name": "Co-channel overlap",
        "severity": "critical",
        "summary": (
            "Equal transmit frequencies and overlapping approved operating or "
            "coordination areas require practitioner review."
        ),
    },
    {
        "id": "RF-002",
        "name": "Close-frequency overlap",
        "severity": "warning",
        "summary": (
            "Non-equal transmit frequencies separated by 12,500 Hz or less and "
            "overlapping approved areas require band-plan-aware review."
        ),
    },
    {
        "id": "RF-003",
        "name": "Reversed repeater pair",
        "severity": "critical",
        "summary": (
            "Non-simplex assignments have inverse receive/transmit pairs; the "
            "relationship may be deliberate in an interoperability plan."
        ),
    },
    {
        "id": "RF-004",
        "name": "Duplicate frequency under different names",
        "severity": "warning",
        "summary": (
            "Different channel names use the same non-null receive/transmit pair "
            "and require contextual review."
        ),
    },
    {
        "id": "RF-008",
        "name": "Subscriber access-code mismatch",
        "severity": "critical",
        "summary": (
            "A directional assignment access code differs from the selected "
            "versioned channel definition or approved subscriber programming profile."
        ),
    },
]
ANALYSIS_STATUS_DEFINITIONS = [
    {
        "id": "RF-007",
        "name": "Area overlap not evaluated",
        "outcome": "not_evaluated",
        "summary": (
            "No frozen approved operating or coordination area was supplied, so "
            "RF-001 and RF-002 did not evaluate the assignment."
        ),
    },
    {
        "id": "RF-STATUS-001",
        "name": "Fixed-frequency deconfliction not applicable",
        "outcome": "not_applicable",
        "summary": (
            "The assignment classification does not use the conventional fixed-frequency "
            "inputs required by one or more RF rules."
        ),
    },
    {
        "id": "RF-STATUS-002",
        "name": "Subscriber access-code comparison not evaluated",
        "outcome": "not_evaluated",
        "summary": (
            "The expected directional access-code value or versioned comparison source "
            "was unavailable."
        ),
    },
]
RULE_BY_ID = {rule["id"]: rule for rule in RULE_DEFINITIONS}
STATUS_BY_ID = {status["id"]: status for status in ANALYSIS_STATUS_DEFINITIONS}
NON_FIXED_CLASSIFICATIONS = {"named_system", "dynamic_pool"}


def rule_set_status(*, approved: bool) -> dict[str, Any]:
    return {
        "rule_set_id": RULE_SET_ID,
        "rule_set_version": RULE_SET_VERSION,
        "approved_for_operational_use": approved,
        "close_frequency_threshold_hz": CLOSE_FREQUENCY_THRESHOLD_HZ,
        "rules": RULE_DEFINITIONS,
        "analysis_statuses": ANALYSIS_STATUS_DEFINITIONS,
        "access_code_source_hierarchy": [
            "selected_versioned_channel_definition",
            "approved_subscriber_programming_profile",
        ],
        "squelch_rule": (
            "CTCSS, DCS, NAC, or equivalent access-code differences never suppress "
            "RF-001 or RF-002."
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
                    "boundary_is_inclusive": True,
                }
    return None


def _compared_input(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item["id"],
        "position": item.get("position"),
        "function": item.get("function", ""),
        "name": item["channel_name"],
        "assignment": item.get("assignment", ""),
        "operating_classification": item["operating_classification"],
        "technology_subtype": item.get("technology_subtype", ""),
        "rx_frequency_hz": item["rx_frequency_hz"],
        "tx_frequency_hz": item["tx_frequency_hz"],
        "rx_squelch": item["rx_squelch"],
        "tx_squelch": item["tx_squelch"],
        "area_count": len(item["areas"]),
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
        "blocking": False,
        "compared_inputs": compared_inputs,
        "evidence": evidence,
        "assumptions": assumptions,
        "explanation": explanation,
        "disclaimer": DISCLAIMER,
    }


def _analysis_status(
    status_id: str,
    *,
    assignment: dict[str, Any],
    affected_rule_ids: list[str],
    evidence: dict[str, Any],
    explanation: str,
) -> dict[str, Any]:
    definition = STATUS_BY_ID[status_id]
    return {
        "status_id": status_id,
        "status_name": definition["name"],
        "outcome": definition["outcome"],
        "rule_set_version": RULE_SET_VERSION,
        "assignment": _compared_input(assignment),
        "affected_rule_ids": affected_rule_ids,
        "evidence": evidence,
        "explanation": explanation,
        "disclaimer": DISCLAIMER,
    }


def _normalized_access_code(value: str) -> str:
    return " ".join(value.casefold().split())


def _access_code_results(
    assignment: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source = assignment.get("expected_access_code_source")
    compared = [_compared_input(assignment)]
    directions = {
        "transmit_only": (("tx", "tx_squelch"),),
        "receive_only": (("rx", "rx_squelch"),),
    }.get(
        assignment["operating_classification"],
        (("rx", "rx_squelch"), ("tx", "tx_squelch")),
    )
    if not source:
        return [], [
            _analysis_status(
                "RF-STATUS-002",
                assignment=assignment,
                affected_rule_ids=["RF-008"],
                evidence={
                    "comparison_source": None,
                    "unevaluated_directions": [
                        direction for direction, _assignment_field in directions
                    ],
                },
                explanation=(
                    f"{assignment['channel_name']} has no selected versioned channel "
                    "definition or approved subscriber programming profile with which to "
                    "compare access codes."
                ),
            )
        ]

    mismatches: list[dict[str, Any]] = []
    unevaluated: list[str] = []
    for direction, assignment_field in directions:
        expected = str(source.get(direction, "") or "").strip()
        entered = str(assignment.get(assignment_field, "") or "").strip()
        if not expected:
            unevaluated.append(direction)
            continue
        if _normalized_access_code(entered) != _normalized_access_code(expected):
            mismatches.append(
                {
                    "direction": direction,
                    "entered_value": entered,
                    "expected_value": expected,
                    "comparison": "normalized case-insensitive literal comparison",
                }
            )

    warnings = []
    if mismatches:
        directions = ", ".join(item["direction"].upper() for item in mismatches)
        warnings.append(
            _warning(
                "RF-008",
                compared_inputs=compared,
                evidence={
                    "comparison_source": source,
                    "mismatches": mismatches,
                    "unevaluated_directions": unevaluated,
                },
                assumptions=[
                    "Receive values compare only to expected receive values; transmit "
                    "values compare only to expected transmit values.",
                    "Access codes are compared as normalized text without inventing "
                    "equivalence between unlike formats.",
                    "This compatibility result is separate from RF overlap and spectrum "
                    "authorization.",
                ],
                explanation=(
                    f"{assignment['channel_name']} has a {directions} subscriber access-code "
                    "mismatch. Subscriber devices may not operate as intended and may require "
                    "special programming or other accommodations."
                ),
            )
        )

    statuses = []
    if unevaluated:
        statuses.append(
            _analysis_status(
                "RF-STATUS-002",
                assignment=assignment,
                affected_rule_ids=["RF-008"],
                evidence={
                    "comparison_source": source,
                    "unevaluated_directions": unevaluated,
                },
                explanation=(
                    f"{assignment['channel_name']} has no authoritative expected "
                    f"{', '.join(direction.upper() for direction in unevaluated)} access-code "
                    "value, so those directions were not evaluated."
                ),
            )
        )
    return warnings, statuses


def evaluate(assignments: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    warnings: list[dict[str, Any]] = []
    analysis_statuses: list[dict[str, Any]] = []
    squelch_assumption = "Access-code values remain evidence and never suppress RF-001 or RF-002."

    for assignment in assignments:
        classification = assignment["operating_classification"]
        if classification in NON_FIXED_CLASSIFICATIONS:
            analysis_statuses.append(
                _analysis_status(
                    "RF-STATUS-001",
                    assignment=assignment,
                    affected_rule_ids=["RF-001", "RF-002", "RF-003", "RF-004"],
                    evidence={
                        "operating_classification": classification,
                        "technology_subtype": assignment.get("technology_subtype", ""),
                    },
                    explanation=(
                        f"{assignment['channel_name']} is explicitly classified as "
                        f"{classification}; conventional fixed-frequency deconfliction "
                        "is not applicable and no conflict-free finding is implied."
                    ),
                )
            )
        elif classification == "receive_only":
            analysis_statuses.append(
                _analysis_status(
                    "RF-STATUS-001",
                    assignment=assignment,
                    affected_rule_ids=["RF-001", "RF-002", "RF-003", "RF-004"],
                    evidence={"operating_classification": classification},
                    explanation=(
                        f"{assignment['channel_name']} is receive-only. Transmit overlap "
                        "and complete-pair rules are not applicable."
                    ),
                )
            )
        elif classification == "not_determined":
            analysis_statuses.append(
                _analysis_status(
                    "RF-STATUS-001",
                    assignment=assignment,
                    affected_rule_ids=["RF-001", "RF-002", "RF-003", "RF-004"],
                    evidence={"operating_classification": classification},
                    explanation=(
                        f"{assignment['channel_name']} has no determined operating "
                        "classification; fixed-frequency rules did not claim a complete result."
                    ),
                )
            )

        if (
            assignment["tx_frequency_hz"] is not None
            and classification in {"fixed_pair", "transmit_only"}
            and not assignment["areas"]
        ):
            analysis_statuses.append(
                _analysis_status(
                    "RF-007",
                    assignment=assignment,
                    affected_rule_ids=["RF-001", "RF-002"],
                    evidence={"approved_area_count": 0},
                    explanation=(
                        "Area overlap not evaluated — no operating or coordination area "
                        f"was supplied for {assignment['channel_name']}."
                    ),
                )
            )

        access_warnings, access_statuses = _access_code_results(assignment)
        warnings.extend(access_warnings)
        analysis_statuses.extend(access_statuses)

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
                "access_code_values_differ": (
                    _normalized_access_code(first["tx_squelch"])
                    != _normalized_access_code(second["tx_squelch"])
                ),
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
                            "use the same transmit frequency inside overlapping approved "
                            "operating or coordination areas."
                        ),
                    )
                )
            elif separation_hz <= CLOSE_FREQUENCY_THRESHOLD_HZ:
                warnings.append(
                    _warning(
                        "RF-002",
                        compared_inputs=compared,
                        evidence={
                            **evidence,
                            "inclusive_screening_threshold_hz": (CLOSE_FREQUENCY_THRESHOLD_HZ),
                        },
                        assumptions=[
                            squelch_assumption,
                            (
                                "The 12,500 Hz value is an inclusive conservative screening "
                                "threshold. Channel spacing varies by band and service."
                            ),
                            (
                                "This rule is not a band-plan-aware adjacency classification, "
                                "interference determination, or equipment-selectivity model."
                            ),
                        ],
                        explanation=(
                            f"{first['channel_name']} and {second['channel_name']} are "
                            f"{separation_hz} Hz apart inside overlapping approved areas. "
                            "A qualified practitioner must evaluate the applicable band plan "
                            "and equipment characteristics."
                        ),
                    )
                )

        if (
            first["operating_classification"] == "fixed_pair"
            and second["operating_classification"] == "fixed_pair"
            and first["rx_frequency_hz"] is not None
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
                    assumptions=[
                        squelch_assumption,
                        (
                            "An inverse pair may be deliberate in a standardized "
                            "interoperability plan, including VTAC repeater configurations."
                        ),
                    ],
                    explanation=(
                        f"{first['channel_name']} and {second['channel_name']} have reversed "
                        "receive/transmit pairs. Verify the applicable interoperability plan "
                        "and assignment context before deciding whether to change either row."
                    ),
                )
            )

        if (
            first["operating_classification"] == "fixed_pair"
            and second["operating_classification"] == "fixed_pair"
            and first["channel_name"].casefold() != second["channel_name"].casefold()
            and first["rx_frequency_hz"] == second["rx_frequency_hz"]
            and first["tx_frequency_hz"] == second["tx_frequency_hz"]
            and first["rx_frequency_hz"] is not None
            and first["tx_frequency_hz"] is not None
        ):
            warnings.append(
                _warning(
                    "RF-004",
                    compared_inputs=compared,
                    evidence={
                        "shared_rx_frequency_hz": first["rx_frequency_hz"],
                        "shared_tx_frequency_hz": first["tx_frequency_hz"],
                        "first_context": _compared_input(first),
                        "second_context": _compared_input(second),
                    },
                    assumptions=[
                        squelch_assumption,
                        (
                            "Aliases and assignments at different locations or operational "
                            "periods may intentionally use the same pair."
                        ),
                    ],
                    explanation=(
                        f"{first['channel_name']} and {second['channel_name']} use the same "
                        "frequency pair under different names. Preserve both assignments and "
                        "review their function, assignment, location, and use context."
                    ),
                )
            )

    return {
        "warnings": sorted(
            warnings,
            key=lambda warning: (
                warning["rule_id"],
                [item["id"] for item in warning["compared_inputs"]],
            ),
        ),
        "analysis_statuses": sorted(
            analysis_statuses,
            key=lambda status: (
                status["status_id"],
                status["assignment"]["id"],
                status["explanation"],
            ),
        ),
    }
