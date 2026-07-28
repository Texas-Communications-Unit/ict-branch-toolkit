from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .coverage import (
    DISCLAIMER,
    EstimateRequest,
    _circle,
    canonical_digest,
    configuration_is_approved,
    configured_coverage_engine,
)
from .models import (
    DirectionalCoverageAnalysis,
    HAATCalculation,
    RFAnalysisInputSnapshot,
)

DIRECTIONAL_RULE_VERSION = "concentric-minimum-v1-provisional"


def directional_rule_is_approved(rule_version: str) -> bool:
    return rule_version in getattr(settings, "ICT_APPROVED_DIRECTIONAL_RULES", [])


def directional_analysis_status() -> dict[str, Any]:
    return {
        "rule_version": DIRECTIONAL_RULE_VERSION,
        "approved_for_operational_use": directional_rule_is_approved(DIRECTIONAL_RULE_VERSION),
        "rule": (
            "Calculate talk-out and talk-in independently. Probable two-way distance is the "
            "smaller nominal distance when both paths are supported and frequency pairs match."
        ),
        "disclaimer": DISCLAIMER,
        "supported_profile_types": [
            "portable",
            "mobile",
            "fixed",
            "cache",
            "gateway",
            "configurable",
        ],
    }


def _required(inputs: dict[str, Any], field: str, source: str):
    value = inputs.get(field)
    if value is None:
        raise ValidationError(
            {
                source: (
                    f"The approved {source.replace('_', ' ')} must contain an explicit "
                    f"{field} value."
                )
            }
        )
    return value


def _path_snapshot(result) -> dict[str, Any]:
    return {
        "calculation_state": result.calculation_state,
        "band": result.band,
        "distances_m": {
            "conservative": result.conservative_distance_m,
            "nominal": result.nominal_distance_m,
            "optimistic": result.optimistic_distance_m,
        },
        "model_snapshot": result.model_snapshot,
        "warnings": result.warnings,
        "exclusions": result.exclusions,
        "explanation": result.explanation,
    }


@transaction.atomic
def create_directional_analysis(
    *,
    haat_calculation: HAATCalculation,
    subscriber_rf_input_snapshot: RFAnalysisInputSnapshot,
    environment: str,
    preset: str,
    actor,
) -> DirectionalCoverageAnalysis:
    haat_calculation = (
        HAATCalculation.objects.select_for_update()
        .select_related(
            "incident",
            "site",
            "rf_input_snapshot__profile_version__profile",
        )
        .get(pk=haat_calculation.pk)
    )
    subscriber_snapshot = (
        RFAnalysisInputSnapshot.objects.select_for_update()
        .select_related("incident", "profile_version__profile")
        .get(pk=subscriber_rf_input_snapshot.pk)
    )
    if haat_calculation.status != HAATCalculation.Status.APPROVED:
        raise ValidationError(
            {"haat_calculation": "Approve and lock the HAAT calculation before analysis."}
        )
    if haat_calculation.calculation_state != HAATCalculation.CalculationState.COMPLETE:
        raise ValidationError(
            {"haat_calculation": "Only a complete HAAT calculation can support analysis."}
        )
    if haat_calculation.incident_id != subscriber_snapshot.incident_id:
        raise ValidationError(
            {"subscriber_rf_input_snapshot": "Both sources must belong to the same incident."}
        )
    if subscriber_snapshot.archived_at is not None:
        raise ValidationError(
            {"subscriber_rf_input_snapshot": "Archived RF input snapshots cannot be analyzed."}
        )
    if subscriber_snapshot.id == haat_calculation.rf_input_snapshot_id:
        raise ValidationError(
            {
                "subscriber_rf_input_snapshot": (
                    "Select a distinct approved subscriber snapshot for the return path."
                )
            }
        )

    infrastructure_snapshot = haat_calculation.rf_input_snapshot
    infrastructure_inputs = infrastructure_snapshot.input_snapshot.get("inputs", {})
    subscriber_inputs = subscriber_snapshot.input_snapshot.get("inputs", {})

    infrastructure_tx_hz = int(
        _required(infrastructure_inputs, "tx_frequency_hz", "haat_calculation")
    )
    infrastructure_rx_hz = int(
        _required(infrastructure_inputs, "rx_frequency_hz", "haat_calculation")
    )
    infrastructure_erp_w = Decimal(
        str(
            _required(
                infrastructure_inputs,
                "effective_radiated_power_w",
                "haat_calculation",
            )
        )
    )
    infrastructure_rx_sensitivity_dbm = Decimal(
        str(
            _required(
                infrastructure_inputs,
                "receiver_sensitivity_dbm",
                "haat_calculation",
            )
        )
    )
    subscriber_tx_hz = int(
        _required(
            subscriber_inputs,
            "tx_frequency_hz",
            "subscriber_rf_input_snapshot",
        )
    )
    subscriber_rx_hz = int(
        _required(
            subscriber_inputs,
            "rx_frequency_hz",
            "subscriber_rf_input_snapshot",
        )
    )
    subscriber_erp_w = Decimal(
        str(
            _required(
                subscriber_inputs,
                "effective_radiated_power_w",
                "subscriber_rf_input_snapshot",
            )
        )
    )
    subscriber_rx_sensitivity_dbm = Decimal(
        str(
            _required(
                subscriber_inputs,
                "receiver_sensitivity_dbm",
                "subscriber_rf_input_snapshot",
            )
        )
    )
    subscriber_height_m = Decimal(
        str(
            _required(
                subscriber_inputs,
                "antenna_center_agl_m",
                "subscriber_rf_input_snapshot",
            )
        )
    )

    input_snapshot = {
        "schema_version": "directional-coverage-input-v1",
        "incident_id": str(haat_calculation.incident_id),
        "site": {
            "id": str(haat_calculation.site_id),
            "name": haat_calculation.site.name,
            "latitude": format(haat_calculation.site.latitude, "f"),
            "longitude": format(haat_calculation.site.longitude, "f"),
        },
        "infrastructure": {
            "rf_input_snapshot_id": str(infrastructure_snapshot.id),
            "input_sha256": infrastructure_snapshot.input_sha256,
            "profile_version_id": str(infrastructure_snapshot.profile_version_id),
            "profile_type": infrastructure_snapshot.profile_version.profile.profile_type,
            "approved_at": infrastructure_snapshot.approved_at.isoformat(),
        },
        "subscriber": {
            "rf_input_snapshot_id": str(subscriber_snapshot.id),
            "input_sha256": subscriber_snapshot.input_sha256,
            "profile_version_id": str(subscriber_snapshot.profile_version_id),
            "profile_type": subscriber_snapshot.profile_version.profile.profile_type,
            "approved_at": subscriber_snapshot.approved_at.isoformat(),
        },
        "haat_calculation": {
            "id": str(haat_calculation.id),
            "result_sha256": haat_calculation.result_sha256,
            "method_version": haat_calculation.method_version,
            "haat_m": format(haat_calculation.haat_m, "f"),
            "approved_at": haat_calculation.approved_at.isoformat(),
        },
        "selected_inputs": {
            "environment": environment,
            "preset": preset,
            "infrastructure_tx_frequency_hz": infrastructure_tx_hz,
            "infrastructure_rx_frequency_hz": infrastructure_rx_hz,
            "subscriber_tx_frequency_hz": subscriber_tx_hz,
            "subscriber_rx_frequency_hz": subscriber_rx_hz,
            "infrastructure_effective_radiated_power_w": format(infrastructure_erp_w, "f"),
            "subscriber_effective_radiated_power_w": format(subscriber_erp_w, "f"),
            "infrastructure_receiver_sensitivity_dbm": format(
                infrastructure_rx_sensitivity_dbm, "f"
            ),
            "subscriber_receiver_sensitivity_dbm": format(subscriber_rx_sensitivity_dbm, "f"),
            "subscriber_antenna_agl_m": format(subscriber_height_m, "f"),
        },
    }

    frequency_exclusions = []
    if infrastructure_tx_hz != subscriber_rx_hz:
        frequency_exclusions.append(
            {
                "code": "talk_out_frequency_mismatch",
                "reason": (
                    "Infrastructure transmit frequency does not match subscriber receive frequency."
                ),
            }
        )
    if subscriber_tx_hz != infrastructure_rx_hz:
        frequency_exclusions.append(
            {
                "code": "talk_in_frequency_mismatch",
                "reason": (
                    "Subscriber transmit frequency does not match infrastructure receive frequency."
                ),
            }
        )

    engine = configured_coverage_engine()
    talk_out = engine.calculate(
        EstimateRequest(
            frequency_hz=infrastructure_tx_hz,
            effective_radiated_power_w=infrastructure_erp_w,
            receiver_sensitivity_dbm=subscriber_rx_sensitivity_dbm,
            haat_m=Decimal(str(haat_calculation.haat_m)),
            environment=environment,
            preset_name=preset,
            receiver_height_m=subscriber_height_m,
        )
    )
    talk_in = engine.calculate(
        EstimateRequest(
            frequency_hz=subscriber_tx_hz,
            effective_radiated_power_w=subscriber_erp_w,
            receiver_sensitivity_dbm=infrastructure_rx_sensitivity_dbm,
            haat_m=Decimal(str(haat_calculation.haat_m)),
            environment=environment,
            preset_name=preset,
            receiver_height_m=subscriber_height_m,
        )
    )

    exclusions = [
        *frequency_exclusions,
        *[
            {"code": f"talk_out_{item['code']}", "reason": item["reason"]}
            for item in talk_out.exclusions
        ],
        *[
            {"code": f"talk_in_{item['code']}", "reason": item["reason"]}
            for item in talk_in.exclusions
        ],
    ]
    warnings = list(dict.fromkeys([*talk_out.warnings, *talk_in.warnings]))
    path_supported = (
        not frequency_exclusions
        and talk_out.nominal_distance_m is not None
        and talk_in.nominal_distance_m is not None
    )
    if path_supported:
        talk_out_distance_m = talk_out.nominal_distance_m
        talk_in_distance_m = talk_in.nominal_distance_m
        probable_two_way_distance_m = min(talk_out_distance_m, talk_in_distance_m)
        calculation_state = DirectionalCoverageAnalysis.CalculationState.COMPLETE
        if talk_out_distance_m < talk_in_distance_m:
            limiting_path = DirectionalCoverageAnalysis.LimitingPath.TALK_OUT
        elif talk_in_distance_m < talk_out_distance_m:
            limiting_path = DirectionalCoverageAnalysis.LimitingPath.TALK_IN
        else:
            limiting_path = DirectionalCoverageAnalysis.LimitingPath.EQUAL
    else:
        talk_out_distance_m = (
            talk_out.nominal_distance_m
            if not any(
                item["code"] == "talk_out_frequency_mismatch" for item in frequency_exclusions
            )
            else None
        )
        talk_in_distance_m = (
            talk_in.nominal_distance_m
            if not any(
                item["code"] == "talk_in_frequency_mismatch" for item in frequency_exclusions
            )
            else None
        )
        probable_two_way_distance_m = None
        calculation_state = DirectionalCoverageAnalysis.CalculationState.UNSUPPORTED
        limiting_path = DirectionalCoverageAnalysis.LimitingPath.NONE

    geometry: dict[str, Any] = {}
    for name, distance_m in (
        ("talk_out", talk_out_distance_m),
        ("talk_in", talk_in_distance_m),
        ("probable_two_way", probable_two_way_distance_m),
    ):
        if distance_m is not None:
            geometry[name] = _circle(
                haat_calculation.site.latitude,
                haat_calculation.site.longitude,
                distance_m,
            )

    preset_version = str(
        talk_out.model_snapshot.get("selected_preset_values", {}).get("version", "")
    )
    model_snapshot = {
        "schema_version": "directional-coverage-model-v1",
        "engine": engine.engine_id,
        "engine_version": engine.engine_version,
        "preset": preset,
        "preset_version": preset_version,
        "rule_version": DIRECTIONAL_RULE_VERSION,
        "two_way_rule": (
            "probable_two_way_nominal_distance_m = "
            "min(talk_out_nominal_distance_m, talk_in_nominal_distance_m)"
        ),
        "talk_out": talk_out.model_snapshot,
        "talk_in": talk_in.model_snapshot,
    }
    explanation = (
        "Talk-out uses infrastructure ERP and subscriber receiver sensitivity. Talk-in uses "
        "subscriber ERP and infrastructure receiver sensitivity. Both paths use the approved "
        "infrastructure HAAT and the subscriber antenna AGL to bound the shared horizon. "
    )
    if path_supported:
        explanation += (
            f"The probable two-way nominal distance is {probable_two_way_distance_m} m, "
            f"limited by {limiting_path.replace('_', '-')}. "
        )
    else:
        explanation += (
            "No probable two-way geometry was produced because at least one directional path "
            "was incomplete, inconsistent, or unsupported. "
        )
    explanation += DISCLAIMER

    result_snapshot = {
        "schema_version": "directional-coverage-result-v1",
        "calculation_state": calculation_state,
        "limiting_path": limiting_path,
        "rule_version": DIRECTIONAL_RULE_VERSION,
        "paths": {
            "talk_out": _path_snapshot(talk_out),
            "talk_in": _path_snapshot(talk_in),
        },
        "probable_two_way": {
            "distance_m": probable_two_way_distance_m,
            "derivation": "minimum_supported_nominal_directional_distance",
        },
        "geometry_wgs84": geometry,
        "input_sha256": canonical_digest(input_snapshot),
        "model_sha256": canonical_digest(model_snapshot),
        "warnings": warnings,
        "exclusions": exclusions,
        "explanation": explanation,
        "disclaimer": DISCLAIMER,
    }
    return DirectionalCoverageAnalysis.objects.create(
        incident=haat_calculation.incident,
        site=haat_calculation.site,
        infrastructure_rf_input_snapshot=infrastructure_snapshot,
        subscriber_rf_input_snapshot=subscriber_snapshot,
        haat_calculation=haat_calculation,
        calculation_state=calculation_state,
        environment=environment,
        engine=engine.engine_id,
        engine_version=engine.engine_version,
        preset=preset,
        preset_version=preset_version,
        rule_version=DIRECTIONAL_RULE_VERSION,
        center_latitude=haat_calculation.site.latitude,
        center_longitude=haat_calculation.site.longitude,
        talk_out_distance_m=talk_out_distance_m,
        talk_in_distance_m=talk_in_distance_m,
        probable_two_way_distance_m=probable_two_way_distance_m,
        limiting_path=limiting_path,
        input_snapshot=input_snapshot,
        input_sha256=canonical_digest(input_snapshot),
        model_snapshot=model_snapshot,
        warnings=warnings,
        exclusions=exclusions,
        explanation=explanation,
        result_snapshot=result_snapshot,
        result_sha256=canonical_digest(result_snapshot),
        created_by=actor,
    )


@transaction.atomic
def approve_directional_analysis(
    analysis: DirectionalCoverageAnalysis, *, actor
) -> DirectionalCoverageAnalysis:
    analysis = DirectionalCoverageAnalysis.objects.select_for_update().get(pk=analysis.pk)
    if analysis.status == DirectionalCoverageAnalysis.Status.APPROVED:
        raise ValidationError("The directional coverage analysis is already approved.")
    if analysis.calculation_state != DirectionalCoverageAnalysis.CalculationState.COMPLETE:
        raise ValidationError("Only complete directional coverage analyses can be approved.")
    if not configuration_is_approved(
        engine=analysis.engine,
        engine_version=analysis.engine_version,
        preset=analysis.preset,
        preset_version=analysis.preset_version,
    ):
        raise ValidationError(
            "The exact coverage engine and preset have not passed the configured practitioner gate."
        )
    if not directional_rule_is_approved(analysis.rule_version):
        raise ValidationError(
            "The exact directional two-way rule has not passed the configured practitioner gate."
        )
    DirectionalCoverageAnalysis.objects.filter(pk=analysis.pk).update(
        status=DirectionalCoverageAnalysis.Status.APPROVED,
        approved_by=actor,
        approved_at=timezone.now(),
    )
    return DirectionalCoverageAnalysis.objects.get(pk=analysis.pk)
