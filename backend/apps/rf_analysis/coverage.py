from __future__ import annotations

import hashlib
import json
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.module_loading import import_string
from rest_framework.exceptions import ValidationError

from .models import CoverageEstimate, HAATCalculation

DISCLAIMER = (
    "Provisional planning estimate only—not a propagation study, frequency-coordination "
    "decision, spectrum authorization, or coverage guarantee."
)

BAND_GROUPS = (
    ("vhf_low", 30_000_000, 88_000_000),
    ("vhf_high", 136_000_000, 174_000_000),
    ("uhf", 380_000_000, 520_000_000),
    ("700_mhz", 698_000_000, 806_000_000),
    ("800_mhz", 806_000_001, 869_000_000),
    ("900_mhz", 896_000_000, 941_000_000),
)

DEFAULT_ENVIRONMENT_MARGINS_DB = {
    CoverageEstimate.Environment.OPEN: Decimal("6"),
    CoverageEstimate.Environment.RURAL: Decimal("10"),
    CoverageEstimate.Environment.SUBURBAN: Decimal("16"),
    CoverageEstimate.Environment.URBAN: Decimal("22"),
    CoverageEstimate.Environment.DENSE_URBAN: Decimal("28"),
}

DEFAULT_PRESETS = {
    "balanced": {
        "version": "balanced-v1-provisional",
        "fade_margin_db": "12",
        "uncertainty_db": "6",
        "receiver_height_m": "1.5",
        "maximum_distance_m": 100_000,
        "distance_rounding_m": 100,
    },
    "conservative": {
        "version": "conservative-v1-provisional",
        "fade_margin_db": "18",
        "uncertainty_db": "6",
        "receiver_height_m": "1.5",
        "maximum_distance_m": 75_000,
        "distance_rounding_m": 100,
    },
}


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _band_for_frequency(frequency_hz: int) -> str | None:
    for name, lower_hz, upper_hz in BAND_GROUPS:
        if lower_hz <= frequency_hz <= upper_hz:
            return name
    return None


def _destination(latitude: float, longitude: float, azimuth_deg: float, distance_m: int):
    earth_radius_m = 6_371_008.8
    angular_distance = distance_m / earth_radius_m
    latitude_rad = math.radians(latitude)
    longitude_rad = math.radians(longitude)
    azimuth_rad = math.radians(azimuth_deg)
    result_latitude = math.asin(
        math.sin(latitude_rad) * math.cos(angular_distance)
        + math.cos(latitude_rad) * math.sin(angular_distance) * math.cos(azimuth_rad)
    )
    result_longitude = longitude_rad + math.atan2(
        math.sin(azimuth_rad) * math.sin(angular_distance) * math.cos(latitude_rad),
        math.cos(angular_distance) - math.sin(latitude_rad) * math.sin(result_latitude),
    )
    normalized_longitude = (math.degrees(result_longitude) + 540) % 360 - 180
    return [round(normalized_longitude, 6), round(math.degrees(result_latitude), 6)]


def _circle(latitude: Decimal, longitude: Decimal, distance_m: int) -> dict[str, Any]:
    coordinates = [
        _destination(float(latitude), float(longitude), azimuth, distance_m)
        for azimuth in range(0, 360, 5)
    ]
    coordinates.append(coordinates[0])
    return {"type": "Polygon", "coordinates": [coordinates]}


def _configured_presets() -> dict[str, dict[str, Any]]:
    configured = getattr(settings, "ICT_COVERAGE_PRESETS", {})
    presets = {name: dict(values) for name, values in DEFAULT_PRESETS.items()}
    if isinstance(configured, dict):
        for name, values in configured.items():
            if isinstance(name, str) and isinstance(values, dict):
                presets[name] = {**presets.get(name, {}), **values}
    return presets


@dataclass(frozen=True)
class EstimateRequest:
    frequency_hz: int
    effective_radiated_power_w: Decimal
    receiver_sensitivity_dbm: Decimal
    haat_m: Decimal
    environment: str
    preset_name: str


@dataclass(frozen=True)
class EstimateResult:
    calculation_state: str
    band: str
    nominal_distance_m: int | None
    conservative_distance_m: int | None
    optimistic_distance_m: int | None
    model_snapshot: dict[str, Any]
    warnings: list[str]
    exclusions: list[dict[str, str]]
    explanation: str


class CoverageEstimateEngine(ABC):
    engine_id = "abstract"
    engine_version = "unconfigured"

    @abstractmethod
    def describe(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def calculate(self, request: EstimateRequest) -> EstimateResult:
        raise NotImplementedError


class ProvisionalFsplHorizonEngine(CoverageEstimateEngine):
    engine_id = "provisional_fspl_horizon"
    engine_version = "fspl-horizon-v1-provisional"

    def describe(self) -> dict[str, Any]:
        return {
            "engine": self.engine_id,
            "engine_version": self.engine_version,
            "approved_for_operational_use": False,
            "disclaimer": DISCLAIMER,
            "supported_band_groups": [
                {"name": name, "lower_hz": lower_hz, "upper_hz": upper_hz}
                for name, lower_hz, upper_hz in BAND_GROUPS
            ],
            "environments": [
                {
                    "name": environment,
                    "additional_margin_db": format(margin, "f"),
                }
                for environment, margin in DEFAULT_ENVIRONMENT_MARGINS_DB.items()
            ],
            "presets": _configured_presets(),
        }

    def _unsupported(
        self,
        *,
        band: str,
        reason: str,
        request: EstimateRequest,
        preset: dict[str, Any] | None,
    ) -> EstimateResult:
        return EstimateResult(
            calculation_state=CoverageEstimate.CalculationState.UNSUPPORTED,
            band=band,
            nominal_distance_m=None,
            conservative_distance_m=None,
            optimistic_distance_m=None,
            model_snapshot={
                **self.describe(),
                "selected_environment": request.environment,
                "selected_preset": request.preset_name,
                "selected_preset_values": preset or {},
            },
            warnings=[DISCLAIMER, reason],
            exclusions=[{"code": "unsupported_input", "reason": reason}],
            explanation=(
                f"No estimate was produced: {reason} The application preserved the unsupported "
                "condition rather than extrapolating or inventing geometry."
            ),
        )

    def calculate(self, request: EstimateRequest) -> EstimateResult:
        band = _band_for_frequency(request.frequency_hz)
        preset = _configured_presets().get(request.preset_name)
        if band is None:
            return self._unsupported(
                band="unsupported",
                reason=(
                    f"{request.frequency_hz} Hz is outside the provisional engine's reviewed "
                    "band groups."
                ),
                request=request,
                preset=preset,
            )
        if request.environment not in DEFAULT_ENVIRONMENT_MARGINS_DB:
            return self._unsupported(
                band=band,
                reason=f"Environment '{request.environment}' is not configured.",
                request=request,
                preset=preset,
            )
        if preset is None:
            return self._unsupported(
                band=band,
                reason=f"Preset '{request.preset_name}' is not configured.",
                request=request,
                preset=None,
            )
        if request.effective_radiated_power_w <= 0:
            return self._unsupported(
                band=band,
                reason="Effective radiated power must be greater than zero.",
                request=request,
                preset=preset,
            )
        if request.receiver_sensitivity_dbm >= 0:
            return self._unsupported(
                band=band,
                reason="Receiver sensitivity must be an explicit negative dBm value.",
                request=request,
                preset=preset,
            )

        environment_margin_db = DEFAULT_ENVIRONMENT_MARGINS_DB[request.environment]
        fade_margin_db = Decimal(str(preset["fade_margin_db"]))
        uncertainty_db = Decimal(str(preset["uncertainty_db"]))
        receiver_height_m = Decimal(str(preset["receiver_height_m"]))
        maximum_distance_m = int(preset["maximum_distance_m"])
        rounding_m = int(preset["distance_rounding_m"])
        if (
            fade_margin_db < 0
            or uncertainty_db < 0
            or receiver_height_m < 0
            or maximum_distance_m <= 0
            or rounding_m <= 0
        ):
            raise ValidationError("Coverage preset values must be non-negative and bounded.")

        erp_dbm = Decimal(str(10 * math.log10(float(request.effective_radiated_power_w) * 1000)))
        eirp_dbm = erp_dbm + Decimal("2.15")
        frequency_mhz = Decimal(request.frequency_hz) / Decimal(1_000_000)
        base_margin_db = environment_margin_db + fade_margin_db

        def budget_distance(margin_db: Decimal) -> Decimal:
            allowed_path_loss_db = eirp_dbm - request.receiver_sensitivity_dbm - margin_db
            distance_km = Decimal(
                str(
                    10
                    ** (
                        (
                            float(allowed_path_loss_db)
                            - 32.44
                            - 20 * math.log10(float(frequency_mhz))
                        )
                        / 20
                    )
                )
            )
            return distance_km * Decimal(1000)

        effective_haat_m = max(request.haat_m, Decimal("0"))
        horizon_m = Decimal(
            str(3570 * (math.sqrt(float(effective_haat_m)) + math.sqrt(float(receiver_height_m))))
        )

        def bounded_and_rounded(distance_m: Decimal) -> int:
            bounded = min(distance_m, horizon_m, Decimal(maximum_distance_m))
            rounded = int(
                (bounded / Decimal(rounding_m)).quantize(Decimal("1")) * Decimal(rounding_m)
            )
            return max(rounding_m, rounded)

        nominal_budget_m = budget_distance(base_margin_db)
        conservative_budget_m = budget_distance(base_margin_db + uncertainty_db)
        optimistic_budget_m = budget_distance(max(Decimal("0"), base_margin_db - uncertainty_db))
        nominal_distance_m = bounded_and_rounded(nominal_budget_m)
        conservative_distance_m = min(
            nominal_distance_m,
            bounded_and_rounded(conservative_budget_m),
        )
        optimistic_distance_m = max(
            nominal_distance_m,
            bounded_and_rounded(optimistic_budget_m),
        )

        limiting_factors = []
        if Decimal(nominal_distance_m) >= horizon_m - Decimal(rounding_m):
            limiting_factors.append("radio_horizon")
        if nominal_distance_m >= maximum_distance_m:
            limiting_factors.append("configured_maximum")
        if not limiting_factors:
            limiting_factors.append("link_budget")

        model_snapshot = {
            **self.describe(),
            "selected_environment": request.environment,
            "selected_preset": request.preset_name,
            "selected_preset_values": {
                **preset,
                "environment_margin_db": format(environment_margin_db, "f"),
            },
            "formulae": {
                "erp_to_eirp": "eirp_dbm = 10*log10(erp_w*1000) + 2.15",
                "free_space_path_loss": (
                    "distance_km = 10 ** ((allowed_path_loss_db - 32.44 "
                    "- 20*log10(frequency_mhz)) / 20)"
                ),
                "planning_horizon": (
                    "distance_km = 3.57 * (sqrt(nonnegative_haat_m) + sqrt(receiver_height_m))"
                ),
                "selection": (
                    "reported distance = minimum(link-budget distance, planning horizon, "
                    "configured maximum), rounded to the configured increment"
                ),
            },
            "intermediate_values": {
                "erp_dbm": f"{erp_dbm:.3f}",
                "eirp_dbm": f"{eirp_dbm:.3f}",
                "frequency_mhz": format(frequency_mhz, "f"),
                "base_margin_db": format(base_margin_db, "f"),
                "horizon_m": f"{horizon_m:.3f}",
                "nominal_budget_m": f"{nominal_budget_m:.3f}",
                "conservative_budget_m": f"{conservative_budget_m:.3f}",
                "optimistic_budget_m": f"{optimistic_budget_m:.3f}",
                "limiting_factors": limiting_factors,
            },
        }
        explanation = (
            f"The {self.engine_version} engine grouped {request.frequency_hz} Hz as {band}, "
            f"applied the {request.environment} environment margin and "
            f"{request.preset_name} preset, and limited the free-space link-budget distance "
            f"by a provisional radio horizon and configured maximum. The nominal estimate is "
            f"{nominal_distance_m} m; the displayed sensitivity range is "
            f"{conservative_distance_m}–{optimistic_distance_m} m. {DISCLAIMER}"
        )
        return EstimateResult(
            calculation_state=CoverageEstimate.CalculationState.COMPLETE,
            band=band,
            nominal_distance_m=nominal_distance_m,
            conservative_distance_m=conservative_distance_m,
            optimistic_distance_m=optimistic_distance_m,
            model_snapshot=model_snapshot,
            warnings=[
                DISCLAIMER,
                (
                    "Environment margins, uncertainty, receiver height, band groupings, and "
                    "distance caps are provisional and require qualified practitioner approval."
                ),
            ],
            exclusions=[],
            explanation=explanation,
        )


def configured_coverage_engine() -> CoverageEstimateEngine:
    engine_class = import_string(settings.ICT_COVERAGE_ENGINE)
    engine = engine_class()
    if not isinstance(engine, CoverageEstimateEngine):
        raise TypeError("ICT_COVERAGE_ENGINE must implement CoverageEstimateEngine.")
    return engine


def configuration_is_approved(
    *,
    engine: str,
    engine_version: str,
    preset: str,
    preset_version: str,
) -> bool:
    for approval in settings.ICT_APPROVED_COVERAGE_CONFIGURATIONS:
        if not isinstance(approval, dict):
            continue
        if (
            approval.get("engine") == engine
            and approval.get("engine_version") == engine_version
            and approval.get("preset") == preset
            and approval.get("preset_version") == preset_version
        ):
            return True
    return False


def coverage_engine_status() -> dict[str, Any]:
    engine = configured_coverage_engine()
    description = engine.describe()
    approved_presets = []
    for preset, values in description["presets"].items():
        preset_version = str(values.get("version", ""))
        if configuration_is_approved(
            engine=engine.engine_id,
            engine_version=engine.engine_version,
            preset=preset,
            preset_version=preset_version,
        ):
            approved_presets.append({"preset": preset, "preset_version": preset_version})
    return {
        **description,
        "approved_for_operational_use": bool(approved_presets),
        "approved_presets": approved_presets,
    }


def _required_snapshot_value(inputs: dict[str, Any], field: str):
    value = inputs.get(field)
    if value is None:
        raise ValidationError(
            {
                "haat_calculation": (
                    f"The approved RF input snapshot must contain an explicit {field} value."
                )
            }
        )
    return value


@transaction.atomic
def create_coverage_estimate(
    *,
    haat_calculation: HAATCalculation,
    environment: str,
    preset: str,
    actor,
) -> CoverageEstimate:
    haat_calculation = (
        HAATCalculation.objects.select_for_update()
        .select_related("incident", "site", "rf_input_snapshot")
        .get(pk=haat_calculation.pk)
    )
    if haat_calculation.status != HAATCalculation.Status.APPROVED:
        raise ValidationError(
            {"haat_calculation": "Approve and lock the HAAT calculation before estimating."}
        )
    if haat_calculation.calculation_state != HAATCalculation.CalculationState.COMPLETE:
        raise ValidationError(
            {"haat_calculation": "Only a complete HAAT calculation can support an estimate."}
        )
    rf_snapshot = haat_calculation.rf_input_snapshot
    inputs = rf_snapshot.input_snapshot.get("inputs", {})
    frequency_hz = int(_required_snapshot_value(inputs, "tx_frequency_hz"))
    effective_radiated_power_w = Decimal(
        str(_required_snapshot_value(inputs, "effective_radiated_power_w"))
    )
    receiver_sensitivity_dbm = Decimal(
        str(_required_snapshot_value(inputs, "receiver_sensitivity_dbm"))
    )
    haat_m = Decimal(str(haat_calculation.haat_m))

    input_snapshot = {
        "schema_version": "coverage-estimate-input-v1",
        "incident_id": str(haat_calculation.incident_id),
        "site": {
            "id": str(haat_calculation.site_id),
            "name": haat_calculation.site.name,
            "latitude": format(haat_calculation.site.latitude, "f"),
            "longitude": format(haat_calculation.site.longitude, "f"),
        },
        "rf_input_snapshot": {
            "id": str(rf_snapshot.id),
            "input_sha256": rf_snapshot.input_sha256,
            "profile_version_id": str(rf_snapshot.profile_version_id),
            "approved_at": rf_snapshot.approved_at.isoformat(),
        },
        "haat_calculation": {
            "id": str(haat_calculation.id),
            "result_sha256": haat_calculation.result_sha256,
            "method_version": haat_calculation.method_version,
            "haat_m": format(haat_calculation.haat_m, "f"),
            "approved_at": haat_calculation.approved_at.isoformat(),
        },
        "selected_inputs": {
            "frequency_hz": frequency_hz,
            "effective_radiated_power_w": format(effective_radiated_power_w, "f"),
            "receiver_sensitivity_dbm": format(receiver_sensitivity_dbm, "f"),
            "environment": environment,
            "preset": preset,
        },
    }
    engine = configured_coverage_engine()
    result = engine.calculate(
        EstimateRequest(
            frequency_hz=frequency_hz,
            effective_radiated_power_w=effective_radiated_power_w,
            receiver_sensitivity_dbm=receiver_sensitivity_dbm,
            haat_m=haat_m,
            environment=environment,
            preset_name=preset,
        )
    )
    geometry = {}
    if result.nominal_distance_m is not None:
        geometry = {
            "conservative": _circle(
                haat_calculation.site.latitude,
                haat_calculation.site.longitude,
                result.conservative_distance_m,
            ),
            "nominal": _circle(
                haat_calculation.site.latitude,
                haat_calculation.site.longitude,
                result.nominal_distance_m,
            ),
            "optimistic": _circle(
                haat_calculation.site.latitude,
                haat_calculation.site.longitude,
                result.optimistic_distance_m,
            ),
        }
    result_snapshot = {
        "schema_version": "coverage-estimate-result-v1",
        "calculation_state": result.calculation_state,
        "band": result.band,
        "distances_m": {
            "conservative": result.conservative_distance_m,
            "nominal": result.nominal_distance_m,
            "optimistic": result.optimistic_distance_m,
        },
        "geometry_wgs84": geometry,
        "input_sha256": canonical_digest(input_snapshot),
        "model_sha256": canonical_digest(result.model_snapshot),
        "warnings": result.warnings,
        "exclusions": result.exclusions,
        "explanation": result.explanation,
        "disclaimer": DISCLAIMER,
    }
    return CoverageEstimate.objects.create(
        incident=haat_calculation.incident,
        site=haat_calculation.site,
        rf_input_snapshot=rf_snapshot,
        haat_calculation=haat_calculation,
        calculation_state=result.calculation_state,
        environment=environment,
        band=result.band,
        engine=engine.engine_id,
        engine_version=engine.engine_version,
        preset=preset,
        preset_version=str(result.model_snapshot["selected_preset_values"].get("version", "")),
        center_latitude=haat_calculation.site.latitude,
        center_longitude=haat_calculation.site.longitude,
        nominal_distance_m=result.nominal_distance_m,
        conservative_distance_m=result.conservative_distance_m,
        optimistic_distance_m=result.optimistic_distance_m,
        input_snapshot=input_snapshot,
        input_sha256=canonical_digest(input_snapshot),
        model_snapshot=result.model_snapshot,
        warnings=result.warnings,
        exclusions=result.exclusions,
        explanation=result.explanation,
        result_snapshot=result_snapshot,
        result_sha256=canonical_digest(result_snapshot),
        created_by=actor,
    )


@transaction.atomic
def approve_coverage_estimate(estimate: CoverageEstimate, *, actor) -> CoverageEstimate:
    estimate = CoverageEstimate.objects.select_for_update().get(pk=estimate.pk)
    if estimate.status == CoverageEstimate.Status.APPROVED:
        raise ValidationError("The coverage estimate is already approved.")
    if estimate.calculation_state != CoverageEstimate.CalculationState.COMPLETE:
        raise ValidationError("Unsupported estimates cannot be approved.")
    if not configuration_is_approved(
        engine=estimate.engine,
        engine_version=estimate.engine_version,
        preset=estimate.preset,
        preset_version=estimate.preset_version,
    ):
        raise ValidationError(
            "This exact coverage engine and preset version has not passed the configured "
            "qualified-practitioner approval gate."
        )
    CoverageEstimate.objects.filter(pk=estimate.pk).update(
        status=CoverageEstimate.Status.APPROVED,
        approved_by=actor,
        approved_at=timezone.now(),
    )
    return CoverageEstimate.objects.get(pk=estimate.pk)
