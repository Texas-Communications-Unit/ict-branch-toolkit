from __future__ import annotations

import logging
import math
import string
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any
from urllib.parse import urlparse

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.module_loading import import_string
from rest_framework.exceptions import ValidationError

from .coverage import DISCLAIMER, canonical_digest
from .models import CoverageEstimate, TerrainAnalysis

TERRAIN_PROFILE_SCHEMA_VERSION = "terrain-profile-v1"
TERRAIN_RESULT_SCHEMA_VERSION = "terrain-analysis-result-v1"
TERRAIN_PROVIDER_VERSION = "terrain-profile-provider-v1"
TERRAIN_ENGINE_ID = "provisional_sampled_line_of_sight"
TERRAIN_ENGINE_VERSION = "sampled-line-of-sight-v1-provisional"
PATH_GENERATION_VERSION = "spherical-destination-mean-earth-radius-v1"
NON_PRODUCTION_LABEL = "NON-PRODUCTION P3.1 TERRAIN DECISION SUPPORT"
TERRAIN_DISCLAIMER = (
    f"{DISCLAIMER} Sampled terrain line-of-sight screening is not diffraction modeling, "
    "field validation, frequency coordination, spectrum authorization, or a guarantee."
)
EARTH_RADIUS_M = Decimal("6371008.8")
EFFECTIVE_EARTH_RADIUS_FACTOR = Decimal("1.333333333")
MATERIAL_DIFFERENCE_PERCENT = Decimal("10")
MATERIAL_DIFFERENCE_MINIMUM_M = 1_000

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TerrainSource:
    provider: str
    provider_version: str
    dataset_product: str
    dataset_version: str
    horizontal_crs: str
    vertical_crs: str
    target_vertical_crs: str
    resolution_m: str | None
    license_terms_url: str
    permitted_use: str
    coverage: dict[str, Any]
    source_content_sha256: str
    offline: bool


@dataclass(frozen=True)
class TerrainProfileBatch:
    source: TerrainSource
    acquisition_state: str
    samples: list[dict[str, Any]]
    transformation: dict[str, Any]
    warnings: list[str]
    retrieved_at: Any


@dataclass(frozen=True)
class TerrainEngineResult:
    analysis_state: str
    result: dict[str, Any]


class TerrainProviderError(Exception):
    """Expected provider failure whose public API message must remain bounded."""


class TerrainProfileProvider(ABC):
    @property
    @abstractmethod
    def source(self) -> TerrainSource:
        raise NotImplementedError

    @property
    def configuration(self) -> dict[str, Any]:
        return {}

    @abstractmethod
    def fetch(self, points: list[dict[str, Any]]) -> TerrainProfileBatch:
        raise NotImplementedError


class DisabledTerrainProfileProvider(TerrainProfileProvider):
    @property
    def source(self) -> TerrainSource:
        return TerrainSource(
            provider="disabled",
            provider_version="",
            dataset_product="No terrain profile source configured",
            dataset_version="",
            horizontal_crs="EPSG:4326",
            vertical_crs="unknown",
            target_vertical_crs="unknown",
            resolution_m=None,
            license_terms_url="",
            permitted_use="No terrain profile source is enabled.",
            coverage={},
            source_content_sha256="",
            offline=True,
        )

    def fetch(self, points: list[dict[str, Any]]) -> TerrainProfileBatch:
        raise TerrainProviderError("No terrain profile provider is configured.")


class SyntheticTerrainProfileProvider(TerrainProfileProvider):
    """Deterministic, network-free profiles for tests and synthetic evaluation."""

    @property
    def source(self) -> TerrainSource:
        descriptor = {
            "provider": "synthetic-offline",
            "provider_version": TERRAIN_PROVIDER_VERSION,
            "dataset_product": "ICT Toolkit deterministic terrain profile fixture",
            "dataset_version": "synthetic-terrain-profile-v1",
        }
        return TerrainSource(
            **descriptor,
            horizontal_crs="EPSG:4326",
            vertical_crs="SYNTHETIC:LOCAL-OFFSET",
            target_vertical_crs="SYNTHETIC:LOCAL",
            resolution_m="30.000",
            license_terms_url=(
                "https://github.com/Texas-Communications-Unit/ict-branch-toolkit/blob/main/"
                "docs/operations/terrain-analysis.md#deterministic-synthetic-provider"
            ),
            permitted_use=(
                "Synthetic fixture data only; not actual terrain and not for operational use."
            ),
            coverage={"type": "synthetic", "extent": "global", "edge_behavior": "mode_controlled"},
            source_content_sha256=canonical_digest(descriptor),
            offline=True,
        )

    @property
    def configuration(self) -> dict[str, Any]:
        return {"synthetic_mode": settings.ICT_SYNTHETIC_TERRAIN_MODE}

    def fetch(self, points: list[dict[str, Any]]) -> TerrainProfileBatch:
        mode = settings.ICT_SYNTHETIC_TERRAIN_MODE
        if mode == "failure":
            raise TerrainProviderError("Synthetic terrain provider failure fixture.")
        maximum_distance = max(Decimal(str(point["distance_m"])) for point in points)
        samples = [
            self._sample(point=point, index=index, mode=mode, maximum_distance=maximum_distance)
            for index, point in enumerate(points)
        ]
        complete = [sample for sample in samples if sample["state"] == "complete"]
        outside = [sample for sample in samples if sample["state"] == "out_of_coverage"]
        if not complete:
            acquisition_state = "out_of_coverage" if outside else "missing"
        elif len(complete) != len(samples):
            acquisition_state = "partial"
        else:
            acquisition_state = "complete"
        warnings = [
            "Synthetic terrain fixture: values do not represent actual terrain and must not be "
            "used for operational decisions."
        ]
        if acquisition_state != "complete":
            warnings.append(
                f"Synthetic terrain fixture returned {acquisition_state} profile coverage."
            )
        return TerrainProfileBatch(
            source=self.source,
            acquisition_state=acquisition_state,
            samples=samples,
            transformation={
                "method": "constant_offset_fixture" if mode == "datum" else "identity",
                "source_vertical_crs": (
                    "SYNTHETIC:LOCAL-OFFSET" if mode == "datum" else "SYNTHETIC:LOCAL"
                ),
                "target_vertical_crs": "SYNTHETIC:LOCAL",
                "offset_m": "10.000" if mode == "datum" else "0.000",
                "grid_or_model": "synthetic-terrain-profile-v1",
                "profile_mode": mode,
            },
            warnings=warnings,
            retrieved_at=timezone.now(),
        )

    @staticmethod
    def _sample(
        *,
        point: dict[str, Any],
        index: int,
        mode: str,
        maximum_distance: Decimal,
    ) -> dict[str, Any]:
        distance = Decimal(str(point["distance_m"]))
        if mode == "out_of_coverage":
            return {
                **point,
                "source_elevation_m": None,
                "terrain_elevation_m": None,
                "state": "out_of_coverage",
                "reason": "Synthetic out-of-coverage fixture.",
            }
        if mode == "missing" and index > 0 and index % 4 == 0:
            return {
                **point,
                "source_elevation_m": None,
                "terrain_elevation_m": None,
                "state": "missing",
                "reason": "Synthetic missing-tile fixture.",
            }
        if mode == "boundary" and distance > maximum_distance * Decimal("0.75"):
            return {
                **point,
                "source_elevation_m": None,
                "terrain_elevation_m": None,
                "state": "out_of_coverage",
                "reason": "Synthetic dataset coverage boundary.",
            }

        baseline = Decimal("100")
        center = maximum_distance * Decimal("0.45")
        width = max(maximum_distance * Decimal("0.08"), Decimal("1"))
        normalized = float((distance - center) / width)
        gaussian = Decimal(str(math.exp(-(normalized**2))))
        if mode == "ridge":
            terrain = baseline + Decimal("120") * gaussian
        elif mode == "valley":
            terrain = baseline - Decimal("60") * gaussian
        else:
            terrain = baseline
        source = terrain - Decimal("10") if mode == "datum" else terrain
        return {
            **point,
            "source_elevation_m": format(source.quantize(Decimal("0.001")), "f"),
            "terrain_elevation_m": format(terrain.quantize(Decimal("0.001")), "f"),
            "state": "complete",
            "reason": "",
        }


class TerrainAnalysisEngine(ABC):
    engine_id = "abstract"
    engine_version = "unconfigured"

    @abstractmethod
    def describe(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def calculate(
        self,
        *,
        analysis: TerrainAnalysis,
        batch: TerrainProfileBatch,
    ) -> TerrainEngineResult:
        raise NotImplementedError


class ProvisionalSampledLineOfSightEngine(TerrainAnalysisEngine):
    engine_id = TERRAIN_ENGINE_ID
    engine_version = TERRAIN_ENGINE_VERSION

    def describe(self) -> dict[str, Any]:
        return {
            "engine": self.engine_id,
            "engine_version": self.engine_version,
            "method": "sampled cumulative line-of-sight screening",
            "approved_for_operational_use": False,
            "capabilities": {
                "terrain_profile": True,
                "sampled_line_of_sight": True,
                "diffraction": False,
                "clutter": False,
                "external_network_required": False,
            },
            "parameters": {
                "effective_earth_radius_factor": format(
                    EFFECTIVE_EARTH_RADIUS_FACTOR,
                    "f",
                ),
                "material_difference_percent": format(MATERIAL_DIFFERENCE_PERCENT, "f"),
                "material_difference_minimum_m": MATERIAL_DIFFERENCE_MINIMUM_M,
            },
            "tested_limits": {
                "maximum_distance_m": settings.ICT_TERRAIN_MAX_DISTANCE_M,
                "maximum_samples": settings.ICT_TERRAIN_MAX_SAMPLES,
                "interpretation": (
                    "Resource-safety bounds for the provisional implementation, not validated "
                    "operational capacity or accuracy."
                ),
            },
            "disclaimer": TERRAIN_DISCLAIMER,
        }

    def _unsupported(
        self,
        *,
        analysis: TerrainAnalysis,
        batch: TerrainProfileBatch,
        reason: str,
    ) -> TerrainEngineResult:
        return TerrainEngineResult(
            analysis_state=TerrainAnalysis.AnalysisState.UNSUPPORTED,
            result={
                "profile": {
                    "acquisition_state": batch.acquisition_state,
                    "requested_distance_m": analysis.maximum_distance_m,
                    "sample_interval_m": analysis.sample_interval_m,
                    "sample_count": len(batch.samples),
                    "complete_sample_count": sum(
                        1 for sample in batch.samples if sample["state"] == "complete"
                    ),
                    "gap_count": 0,
                    "edge_effect": False,
                    "samples": batch.samples,
                    "sample_sha256": canonical_digest(batch.samples),
                },
                "comparison": {
                    "phase2_nominal_distance_m": analysis.coverage_estimate.nominal_distance_m,
                    "terrain_continuous_los_distance_m": None,
                    "difference_m": None,
                    "difference_percent": None,
                    "materially_different": None,
                },
                "warnings": [*batch.warnings, reason, TERRAIN_DISCLAIMER],
                "exclusions": [{"code": "unsupported_condition", "reason": reason}],
                "explanation": (
                    f"No sampled line-of-sight comparison was produced: {reason} The earlier "
                    "Phase 2 estimate remains unchanged and visible."
                ),
            },
        )

    def calculate(
        self,
        *,
        analysis: TerrainAnalysis,
        batch: TerrainProfileBatch,
    ) -> TerrainEngineResult:
        source_resolution = (
            Decimal(batch.source.resolution_m) if batch.source.resolution_m is not None else None
        )
        if source_resolution is None:
            return self._unsupported(
                analysis=analysis,
                batch=batch,
                reason="The selected terrain source does not declare a resolution.",
            )
        if Decimal(analysis.sample_interval_m) < source_resolution:
            return self._unsupported(
                analysis=analysis,
                batch=batch,
                reason=(
                    f"The requested {analysis.sample_interval_m} m interval is finer than the "
                    f"declared {source_resolution} m source resolution."
                ),
            )

        complete_samples = [
            sample
            for sample in batch.samples
            if sample["state"] == "complete" and sample["terrain_elevation_m"] is not None
        ]
        if len(complete_samples) < 2:
            return self._unsupported(
                analysis=analysis,
                batch=batch,
                reason="The terrain source returned fewer than two usable profile samples.",
            )

        antenna_amsl = analysis.coverage_estimate.haat_calculation.antenna_amsl_m
        if antenna_amsl is None:
            return self._unsupported(
                analysis=analysis,
                batch=batch,
                reason="The selected HAAT evidence does not retain antenna AMSL height.",
            )
        antenna_amsl = Decimal(antenna_amsl)

        maximum_obstruction_slope: Decimal | None = None
        continuous_clear = True
        continuous_distance = 0
        first_obstruction_distance: int | None = None
        obstruction_count = 0
        gap_count = 0
        profile = []
        effective_radius = EARTH_RADIUS_M * EFFECTIVE_EARTH_RADIUS_FACTOR

        for sample in batch.samples:
            distance = Decimal(str(sample["distance_m"]))
            evidence = {
                "distance_m": int(distance),
                "latitude": sample["latitude"],
                "longitude": sample["longitude"],
                "state": sample["state"],
                "source_elevation_m": sample["source_elevation_m"],
                "terrain_elevation_m": sample["terrain_elevation_m"],
                "reason": sample["reason"],
                "visible": None,
                "curvature_drop_m": None,
                "receiver_slope": None,
                "obstruction_slope": None,
            }
            if distance == 0 and sample["state"] == "complete":
                evidence["visible"] = True
                evidence["curvature_drop_m"] = "0.000"
                profile.append(evidence)
                continue
            if sample["state"] != "complete" or sample["terrain_elevation_m"] is None:
                gap_count += 1
                continuous_clear = False
                if first_obstruction_distance is None:
                    first_obstruction_distance = int(distance)
                profile.append(evidence)
                continue

            terrain = Decimal(str(sample["terrain_elevation_m"]))
            curvature_drop = (distance * distance) / (Decimal("2") * effective_radius)
            apparent_terrain = terrain - curvature_drop
            obstruction_slope = (apparent_terrain + analysis.clearance_m - antenna_amsl) / distance
            receiver_slope = (
                apparent_terrain + analysis.receiver_height_m - antenna_amsl
            ) / distance
            visible = (
                maximum_obstruction_slope is None or receiver_slope >= maximum_obstruction_slope
            )
            if not visible:
                obstruction_count += 1
                continuous_clear = False
                if first_obstruction_distance is None:
                    first_obstruction_distance = int(distance)
            if continuous_clear:
                continuous_distance = int(distance)
            maximum_obstruction_slope = (
                obstruction_slope
                if maximum_obstruction_slope is None
                else max(maximum_obstruction_slope, obstruction_slope)
            )
            evidence.update(
                {
                    "visible": visible,
                    "curvature_drop_m": f"{curvature_drop:.3f}",
                    "receiver_slope": f"{receiver_slope:.9f}",
                    "obstruction_slope": f"{obstruction_slope:.9f}",
                }
            )
            profile.append(evidence)

        phase2_distance = analysis.coverage_estimate.nominal_distance_m
        difference = continuous_distance - phase2_distance if phase2_distance is not None else None
        difference_percent = (
            (Decimal(difference) / Decimal(phase2_distance) * Decimal("100"))
            if difference is not None and phase2_distance
            else None
        )
        material_threshold = (
            max(
                MATERIAL_DIFFERENCE_MINIMUM_M,
                round(phase2_distance * float(MATERIAL_DIFFERENCE_PERCENT) / 100),
            )
            if phase2_distance is not None
            else None
        )
        materially_different = (
            abs(difference) >= material_threshold
            if difference is not None and material_threshold is not None
            else None
        )
        analysis_state = (
            TerrainAnalysis.AnalysisState.PARTIAL
            if gap_count or batch.acquisition_state != "complete"
            else TerrainAnalysis.AnalysisState.COMPLETE
        )
        edge_effect = any(sample["state"] == "out_of_coverage" for sample in batch.samples)
        warnings = [
            *batch.warnings,
            (
                f"Features narrower than the declared {source_resolution} m source resolution "
                "may not be detected."
            ),
            TERRAIN_DISCLAIMER,
        ]
        if gap_count:
            warnings.append(
                "Profile gaps stop the continuous clear-distance result; no gap is interpolated."
            )
        if edge_effect:
            warnings.append(
                "The requested path reaches a dataset coverage edge; results beyond the last "
                "complete sample are unsupported."
            )
        comparison_message = (
            (
                f"The sampled continuous line-of-sight distance is {continuous_distance} m, "
                f"{abs(difference)} m {'longer' if difference > 0 else 'shorter'} than the "
                f"Phase 2 nominal estimate of {phase2_distance} m."
            )
            if difference not in {None, 0}
            else (
                f"The sampled continuous line-of-sight distance and Phase 2 nominal estimate "
                f"are both {phase2_distance} m."
                if difference == 0
                else "The Phase 2 estimate does not contain a comparable nominal distance."
            )
        )
        if materially_different is True:
            comparison_message += (
                " The difference exceeds the provisional material-difference threshold and "
                "requires qualified review."
            )
        elif materially_different is False:
            comparison_message += (
                " The difference does not exceed the provisional material-difference threshold."
            )

        return TerrainEngineResult(
            analysis_state=analysis_state,
            result={
                "profile": {
                    "acquisition_state": batch.acquisition_state,
                    "requested_distance_m": analysis.maximum_distance_m,
                    "sample_interval_m": analysis.sample_interval_m,
                    "sample_count": len(batch.samples),
                    "complete_sample_count": len(complete_samples),
                    "gap_count": gap_count,
                    "edge_effect": edge_effect,
                    "samples": profile,
                    "sample_sha256": canonical_digest(batch.samples),
                },
                "line_of_sight": {
                    "continuous_clear_distance_m": continuous_distance,
                    "first_obstruction_or_gap_distance_m": first_obstruction_distance,
                    "obstruction_count": obstruction_count,
                    "receiver_height_m": format(analysis.receiver_height_m, "f"),
                    "clearance_m": format(analysis.clearance_m, "f"),
                    "effective_earth_radius_factor": format(
                        EFFECTIVE_EARTH_RADIUS_FACTOR,
                        "f",
                    ),
                },
                "comparison": {
                    "phase2_nominal_distance_m": phase2_distance,
                    "terrain_continuous_los_distance_m": continuous_distance,
                    "difference_m": difference,
                    "difference_percent": (
                        f"{difference_percent:.3f}" if difference_percent is not None else None
                    ),
                    "material_threshold_m": material_threshold,
                    "materially_different": materially_different,
                    "interpretation": comparison_message,
                    "layer_behavior": (
                        "Terrain evidence is a separate directional comparison and never "
                        "replaces the Phase 2 estimate."
                    ),
                },
                "supported_conditions": [
                    "One source-aware sampled terrain profile at an explicit azimuth.",
                    "Cumulative sampled line-of-sight screening with declared receiver height.",
                    "Effective-Earth-radius curvature adjustment documented by engine version.",
                ],
                "unsupported_conditions": [
                    "Diffraction, clutter, vegetation, buildings, reflections, and multipath.",
                    "Obstructions narrower than the declared source resolution.",
                    "Locations beyond source coverage or across missing samples.",
                    "Regulatory studies, frequency coordination, and coverage guarantees.",
                ],
                "warnings": warnings,
                "exclusions": [
                    {
                        "code": "profile_gap",
                        "count": gap_count,
                        "reason": "Missing or out-of-coverage samples are not interpolated.",
                    }
                ]
                if gap_count
                else [],
                "explanation": (
                    f"{comparison_message} The {self.engine_version} engine evaluated "
                    f"{len(batch.samples)} samples at azimuth {analysis.azimuth_deg} degrees. "
                    f"{TERRAIN_DISCLAIMER}"
                ),
            },
        )


def configured_terrain_provider() -> TerrainProfileProvider:
    provider_class = import_string(settings.ICT_TERRAIN_PROVIDER)
    provider = provider_class()
    if not isinstance(provider, TerrainProfileProvider):
        raise TypeError("ICT_TERRAIN_PROVIDER must implement TerrainProfileProvider.")
    return provider


def configured_terrain_engine() -> TerrainAnalysisEngine:
    engine_class = import_string(settings.ICT_TERRAIN_ENGINE)
    engine = engine_class()
    if not isinstance(engine, TerrainAnalysisEngine):
        raise TypeError("ICT_TERRAIN_ENGINE must implement TerrainAnalysisEngine.")
    return engine


def configuration_is_approved(
    *,
    source: TerrainSource,
    engine: TerrainAnalysisEngine,
) -> bool:
    if source.provider == "disabled":
        return False
    required_text = (
        source.provider,
        source.provider_version,
        source.dataset_product,
        source.dataset_version,
        source.horizontal_crs,
        source.vertical_crs,
        source.target_vertical_crs,
        source.permitted_use,
    )
    if any(not value.strip() for value in required_text):
        return False
    parsed = urlparse(source.license_terms_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    if (
        len(source.source_content_sha256) != 64
        or any(character not in string.hexdigits for character in source.source_content_sha256)
        or source.source_content_sha256 != source.source_content_sha256.lower()
    ):
        return False
    if source.resolution_m is None:
        return False
    try:
        if not Decimal(source.resolution_m).is_finite() or Decimal(source.resolution_m) <= 0:
            return False
    except ArithmeticError:
        return False
    required = {
        "provider": source.provider,
        "provider_version": source.provider_version,
        "dataset_product": source.dataset_product,
        "dataset_version": source.dataset_version,
        "source_content_sha256": source.source_content_sha256,
        "engine": engine.engine_id,
        "engine_version": engine.engine_version,
    }
    return any(
        all(configuration.get(field) == value for field, value in required.items())
        for configuration in settings.ICT_APPROVED_TERRAIN_CONFIGURATIONS
    )


def terrain_status() -> dict[str, Any]:
    provider = configured_terrain_provider()
    engine = configured_terrain_engine()
    approved = configuration_is_approved(source=provider.source, engine=engine)
    return {
        "provider": asdict(provider.source),
        "provider_configuration": provider.configuration,
        "engine": engine.describe(),
        "configured": provider.source.provider != "disabled",
        "approved_for_analysis": approved,
        "available": provider.source.provider != "disabled" and approved,
        "execution_model": "explicit synchronous staged job",
        "cancellation_boundary": (
            "Queued work can be cancelled before execution. Once a run starts, the request "
            "must finish; no background worker is configured."
        ),
        "resource_safety_limits": {
            "maximum_distance_m": settings.ICT_TERRAIN_MAX_DISTANCE_M,
            "maximum_samples": settings.ICT_TERRAIN_MAX_SAMPLES,
        },
        "warning": (
            ""
            if approved
            else (
                "No terrain profile provider is configured."
                if provider.source.provider == "disabled"
                else "The exact terrain source, dataset, and engine are not allowlisted."
            )
        ),
        "classification": NON_PRODUCTION_LABEL,
        "disclaimer": TERRAIN_DISCLAIMER,
    }


def _destination_point(
    *,
    latitude: Decimal,
    longitude: Decimal,
    azimuth_deg: Decimal,
    distance_m: int,
) -> tuple[str, str]:
    angular = distance_m / float(EARTH_RADIUS_M)
    bearing = math.radians(float(azimuth_deg))
    lat1 = math.radians(float(latitude))
    lon1 = math.radians(float(longitude))
    lat2 = math.asin(
        math.sin(lat1) * math.cos(angular) + math.cos(lat1) * math.sin(angular) * math.cos(bearing)
    )
    lon2 = (
        lon1
        + math.atan2(
            math.sin(bearing) * math.sin(angular) * math.cos(lat1),
            math.cos(angular) - math.sin(lat1) * math.sin(lat2),
        )
        + (3 * math.pi)
    ) % (2 * math.pi) - math.pi
    return f"{math.degrees(lat2):.6f}", f"{math.degrees(lon2):.6f}"


def _profile_points(analysis: TerrainAnalysis) -> list[dict[str, Any]]:
    distances = list(range(0, analysis.maximum_distance_m, analysis.sample_interval_m))
    if not distances or distances[-1] != analysis.maximum_distance_m:
        distances.append(analysis.maximum_distance_m)
    if len(distances) > settings.ICT_TERRAIN_MAX_SAMPLES:
        raise ValidationError(
            {
                "sample_interval_m": (
                    f"The requested path needs {len(distances)} samples; the configured limit "
                    f"is {settings.ICT_TERRAIN_MAX_SAMPLES}."
                )
            }
        )
    points = []
    for distance in distances:
        latitude, longitude = _destination_point(
            latitude=analysis.site.latitude,
            longitude=analysis.site.longitude,
            azimuth_deg=analysis.azimuth_deg,
            distance_m=distance,
        )
        points.append(
            {
                "distance_m": distance,
                "azimuth_deg": format(analysis.azimuth_deg, "f"),
                "latitude": latitude,
                "longitude": longitude,
            }
        )
    return points


def _validate_coverage(coverage_estimate: CoverageEstimate) -> None:
    if coverage_estimate.status != CoverageEstimate.Status.APPROVED:
        raise ValidationError(
            {"coverage_estimate": "Approve the Phase 2 coverage estimate before terrain analysis."}
        )
    if coverage_estimate.calculation_state != CoverageEstimate.CalculationState.COMPLETE:
        raise ValidationError(
            {"coverage_estimate": "Only a complete Phase 2 estimate can be compared."}
        )
    if coverage_estimate.haat_calculation.antenna_amsl_m is None:
        raise ValidationError(
            {"coverage_estimate": "The selected estimate lacks retained antenna AMSL evidence."}
        )


def _validate_profile_batch(
    *,
    batch: TerrainProfileBatch,
    expected_source: TerrainSource,
    requested_points: list[dict[str, Any]],
) -> None:
    if batch.source != expected_source:
        raise ValidationError("The terrain provider returned an unexpected source descriptor.")
    if batch.acquisition_state not in {"complete", "partial", "missing", "out_of_coverage"}:
        raise ValidationError("The terrain provider returned an unsupported acquisition state.")
    if len(batch.samples) != len(requested_points):
        raise ValidationError("The terrain provider returned an unexpected sample count.")
    if not isinstance(batch.transformation, dict):
        raise ValidationError("The terrain provider omitted structured transformation evidence.")
    if not timezone.is_aware(batch.retrieved_at):
        raise ValidationError("The terrain provider returned a retrieval time without a timezone.")
    if not isinstance(batch.warnings, list) or any(
        not isinstance(warning, str) for warning in batch.warnings
    ):
        raise ValidationError("The terrain provider returned invalid warning evidence.")

    for requested, sample in zip(requested_points, batch.samples, strict=True):
        if not isinstance(sample, dict):
            raise ValidationError("The terrain provider returned an invalid sample.")
        if any(
            str(sample.get(field)) != str(requested[field])
            for field in ("distance_m", "azimuth_deg", "latitude", "longitude")
        ):
            raise ValidationError(
                "The terrain provider changed a requested path coordinate or distance."
            )
        if sample.get("state") not in {"complete", "missing", "out_of_coverage"}:
            raise ValidationError("The terrain provider returned an unsupported sample state.")
        if not isinstance(sample.get("reason", ""), str):
            raise ValidationError("The terrain provider returned an invalid sample reason.")
        source_elevation = sample.get("source_elevation_m")
        terrain_elevation = sample.get("terrain_elevation_m")
        if sample["state"] == "complete":
            if source_elevation is None or terrain_elevation is None:
                raise ValidationError("A complete terrain sample omitted elevation evidence.")
            try:
                if not all(
                    Decimal(str(value)).is_finite()
                    for value in (source_elevation, terrain_elevation)
                ):
                    raise ValidationError("A terrain sample contained a non-finite elevation.")
            except ArithmeticError as error:
                raise ValidationError("A terrain sample contained an invalid elevation.") from error
        elif source_elevation is not None or terrain_elevation is not None:
            raise ValidationError(
                "A missing or out-of-coverage sample cannot contain elevation evidence."
            )


def _input_snapshot(
    *,
    coverage_estimate: CoverageEstimate,
    azimuth_deg: Decimal,
    maximum_distance_m: int,
    sample_interval_m: int,
    receiver_height_m: Decimal,
    clearance_m: Decimal,
    provider: TerrainProfileProvider,
    engine: TerrainAnalysisEngine,
) -> dict[str, Any]:
    return {
        "schema_version": "terrain-analysis-input-v1",
        "application_version": settings.APP_VERSION,
        "incident_id": str(coverage_estimate.incident_id),
        "site": {
            "id": str(coverage_estimate.site_id),
            "latitude": format(coverage_estimate.site.latitude, "f"),
            "longitude": format(coverage_estimate.site.longitude, "f"),
        },
        "phase2_coverage_estimate": {
            "id": str(coverage_estimate.id),
            "result_sha256": coverage_estimate.result_sha256,
            "engine": coverage_estimate.engine,
            "engine_version": coverage_estimate.engine_version,
            "nominal_distance_m": coverage_estimate.nominal_distance_m,
            "conservative_distance_m": coverage_estimate.conservative_distance_m,
            "optimistic_distance_m": coverage_estimate.optimistic_distance_m,
        },
        "haat_evidence": {
            "id": str(coverage_estimate.haat_calculation_id),
            "result_sha256": coverage_estimate.haat_calculation.result_sha256,
            "antenna_amsl_m": format(
                coverage_estimate.haat_calculation.antenna_amsl_m,
                "f",
            ),
        },
        "terrain_source": asdict(provider.source),
        "provider_configuration": provider.configuration,
        "terrain_engine": engine.describe(),
        "path_generation": {
            "method_version": PATH_GENERATION_VERSION,
            "coordinate_reference": "EPSG:4326",
            "earth_radius_m": format(EARTH_RADIUS_M, "f"),
            "coordinate_rounding_decimal_places": 6,
        },
        "parameters": {
            "azimuth_deg": format(azimuth_deg, "f"),
            "maximum_distance_m": maximum_distance_m,
            "sample_interval_m": sample_interval_m,
            "receiver_height_m": format(receiver_height_m, "f"),
            "clearance_m": format(clearance_m, "f"),
        },
    }


@transaction.atomic
def queue_terrain_analysis(
    *,
    coverage_estimate: CoverageEstimate,
    azimuth_deg: Decimal,
    maximum_distance_m: int,
    sample_interval_m: int,
    receiver_height_m: Decimal,
    clearance_m: Decimal,
    actor,
    supersedes: TerrainAnalysis | None = None,
) -> TerrainAnalysis:
    coverage_estimate = (
        CoverageEstimate.objects.select_for_update()
        .select_related("incident", "site", "haat_calculation")
        .get(pk=coverage_estimate.pk)
    )
    _validate_coverage(coverage_estimate)
    if maximum_distance_m > settings.ICT_TERRAIN_MAX_DISTANCE_M:
        raise ValidationError(
            {
                "maximum_distance_m": (
                    f"The configured terrain-analysis limit is "
                    f"{settings.ICT_TERRAIN_MAX_DISTANCE_M} m."
                )
            }
        )
    sample_count = math.ceil(maximum_distance_m / sample_interval_m) + 1
    if sample_count > settings.ICT_TERRAIN_MAX_SAMPLES:
        raise ValidationError(
            {
                "sample_interval_m": (
                    f"The requested path needs {sample_count} samples; the configured limit is "
                    f"{settings.ICT_TERRAIN_MAX_SAMPLES}."
                )
            }
        )
    provider = configured_terrain_provider()
    engine = configured_terrain_engine()
    if not configuration_is_approved(source=provider.source, engine=engine):
        raise ValidationError(
            "The exact terrain source, dataset, and engine have not passed the configured "
            "qualified GIS/RF and maintainer gate."
        )
    if supersedes is not None:
        if supersedes.incident_id != coverage_estimate.incident_id:
            raise ValidationError({"supersedes": "Retry lineage cannot cross incidents."})
        if supersedes.job_state not in {
            TerrainAnalysis.JobState.FAILED,
            TerrainAnalysis.JobState.CANCELLED,
        }:
            raise ValidationError({"supersedes": "Only failed or cancelled work can be retried."})
    input_snapshot = _input_snapshot(
        coverage_estimate=coverage_estimate,
        azimuth_deg=azimuth_deg,
        maximum_distance_m=maximum_distance_m,
        sample_interval_m=sample_interval_m,
        receiver_height_m=receiver_height_m,
        clearance_m=clearance_m,
        provider=provider,
        engine=engine,
    )
    return TerrainAnalysis.objects.create(
        incident=coverage_estimate.incident,
        site=coverage_estimate.site,
        coverage_estimate=coverage_estimate,
        supersedes=supersedes,
        provider=provider.source.provider,
        provider_version=provider.source.provider_version,
        dataset_product=provider.source.dataset_product,
        dataset_version=provider.source.dataset_version,
        engine=engine.engine_id,
        engine_version=engine.engine_version,
        app_version=settings.APP_VERSION,
        azimuth_deg=azimuth_deg,
        maximum_distance_m=maximum_distance_m,
        sample_interval_m=sample_interval_m,
        receiver_height_m=receiver_height_m,
        clearance_m=clearance_m,
        input_snapshot=input_snapshot,
        input_sha256=canonical_digest(input_snapshot),
        created_by=actor,
    )


def _mark_failed(analysis: TerrainAnalysis, *, code: str, message: str) -> None:
    analysis.job_state = TerrainAnalysis.JobState.FAILED
    analysis.progress_step = "failed"
    analysis.completed_at = timezone.now()
    analysis.failure_code = code[:80]
    analysis.failure_message = message[:240]
    analysis.save(
        update_fields=[
            "job_state",
            "progress_step",
            "completed_at",
            "failure_code",
            "failure_message",
            "updated_at",
        ]
    )


def run_terrain_analysis(analysis: TerrainAnalysis) -> TerrainAnalysis:
    with transaction.atomic():
        analysis = (
            TerrainAnalysis.objects.select_for_update()
            .select_related("incident", "site", "coverage_estimate__haat_calculation")
            .get(pk=analysis.pk)
        )
        if analysis.job_state != TerrainAnalysis.JobState.QUEUED:
            raise ValidationError("Only queued terrain work can be run.")
        analysis.job_state = TerrainAnalysis.JobState.RUNNING
        analysis.progress_step = "validating_sources"
        analysis.progress_percent = 10
        analysis.started_at = timezone.now()
        analysis.save(
            update_fields=[
                "job_state",
                "progress_step",
                "progress_percent",
                "started_at",
                "updated_at",
            ]
        )

    try:
        _validate_coverage(analysis.coverage_estimate)
        provider = configured_terrain_provider()
        engine = configured_terrain_engine()
        if not configuration_is_approved(source=provider.source, engine=engine):
            _mark_failed(
                analysis,
                code="configuration_not_approved",
                message=(
                    "The configured terrain source, dataset, or engine is no longer allowlisted."
                ),
            )
            return TerrainAnalysis.objects.get(pk=analysis.pk)
        current_input = _input_snapshot(
            coverage_estimate=analysis.coverage_estimate,
            azimuth_deg=analysis.azimuth_deg,
            maximum_distance_m=analysis.maximum_distance_m,
            sample_interval_m=analysis.sample_interval_m,
            receiver_height_m=analysis.receiver_height_m,
            clearance_m=analysis.clearance_m,
            provider=provider,
            engine=engine,
        )
        if canonical_digest(current_input) != analysis.input_sha256:
            _mark_failed(
                analysis,
                code="configuration_changed",
                message=(
                    "Terrain configuration or selected Phase 2 evidence changed after queueing. "
                    "Create a new terrain analysis from current approved sources."
                ),
            )
            return TerrainAnalysis.objects.get(pk=analysis.pk)
        points = _profile_points(analysis)
        batch = provider.fetch(points)
        _validate_profile_batch(
            batch=batch,
            expected_source=provider.source,
            requested_points=points,
        )
        calculated = engine.calculate(analysis=analysis, batch=batch)
        result = {
            "schema_version": TERRAIN_RESULT_SCHEMA_VERSION,
            "classification": NON_PRODUCTION_LABEL,
            "application_version": analysis.app_version,
            "input_sha256": analysis.input_sha256,
            "source": {
                **asdict(batch.source),
                "retrieved_at": batch.retrieved_at.isoformat(),
                "transformation": batch.transformation,
                "acquisition_state": batch.acquisition_state,
            },
            "algorithm": engine.describe(),
            **calculated.result,
            "disclaimer": TERRAIN_DISCLAIMER,
        }
        with transaction.atomic():
            analysis = TerrainAnalysis.objects.select_for_update().get(pk=analysis.pk)
            analysis.analysis_state = calculated.analysis_state
            analysis.result_snapshot = result
            analysis.result_sha256 = canonical_digest(result)
            analysis.job_state = TerrainAnalysis.JobState.COMPLETE
            analysis.progress_step = "complete"
            analysis.progress_percent = 100
            analysis.completed_at = timezone.now()
            analysis.save(
                update_fields=[
                    "analysis_state",
                    "result_snapshot",
                    "result_sha256",
                    "job_state",
                    "progress_step",
                    "progress_percent",
                    "completed_at",
                    "updated_at",
                ]
            )
        return analysis
    except TerrainProviderError:
        logger.warning("Terrain provider failed for analysis %s.", analysis.pk)
        _mark_failed(
            analysis,
            code="terrain_provider_unavailable",
            message=(
                "The terrain source was unavailable. Core planning remains available; retry "
                "from a new queued record after the provider is restored."
            ),
        )
        return TerrainAnalysis.objects.get(pk=analysis.pk)
    except ValidationError:
        logger.warning("Terrain source validation failed for analysis %s.", analysis.pk)
        _mark_failed(
            analysis,
            code="terrain_source_invalid",
            message="Selected sources no longer satisfy terrain-analysis requirements.",
        )
        return TerrainAnalysis.objects.get(pk=analysis.pk)
    except Exception:
        logger.exception("Terrain analysis internal failure for analysis %s.", analysis.pk)
        _mark_failed(
            analysis,
            code="terrain_internal_error",
            message=(
                "Terrain analysis failed without changing retained source evidence. Review "
                "protected server logs and retry from a new queued record."
            ),
        )
        return TerrainAnalysis.objects.get(pk=analysis.pk)


@transaction.atomic
def cancel_terrain_analysis(analysis: TerrainAnalysis) -> TerrainAnalysis:
    analysis = TerrainAnalysis.objects.select_for_update().get(pk=analysis.pk)
    if analysis.job_state != TerrainAnalysis.JobState.QUEUED:
        raise ValidationError("Only queued terrain work can be cancelled.")
    analysis.job_state = TerrainAnalysis.JobState.CANCELLED
    analysis.progress_step = "cancelled"
    analysis.completed_at = timezone.now()
    analysis.failure_code = "cancelled_by_user"
    analysis.failure_message = "The queued terrain run was cancelled before execution."
    analysis.save(
        update_fields=[
            "job_state",
            "progress_step",
            "completed_at",
            "failure_code",
            "failure_message",
            "updated_at",
        ]
    )
    return analysis


def terrain_stale_reasons(analysis: TerrainAnalysis) -> list[str]:
    provider = configured_terrain_provider()
    engine = configured_terrain_engine()
    reasons = []
    retained_source = analysis.input_snapshot.get("terrain_source", {})
    retained_engine = analysis.input_snapshot.get("terrain_engine", {})
    retained_provider_configuration = analysis.input_snapshot.get("provider_configuration", {})
    if not configuration_is_approved(source=provider.source, engine=engine):
        reasons.append("terrain_configuration_no_longer_approved")
    if asdict(provider.source) != retained_source:
        reasons.append("terrain_source_changed")
    if provider.configuration != retained_provider_configuration:
        reasons.append("terrain_provider_configuration_changed")
    if engine.describe() != retained_engine:
        reasons.append("terrain_engine_configuration_changed")
    if analysis.coverage_estimate.result_sha256 != analysis.input_snapshot.get(
        "phase2_coverage_estimate", {}
    ).get("result_sha256"):
        reasons.append("phase2_estimate_digest_changed")
    if analysis.coverage_estimate.haat_calculation.result_sha256 != analysis.input_snapshot.get(
        "haat_evidence", {}
    ).get("result_sha256"):
        reasons.append("haat_result_digest_changed")
    retained_site = analysis.input_snapshot.get("site", {})
    if format(analysis.site.latitude, "f") != retained_site.get("latitude") or format(
        analysis.site.longitude, "f"
    ) != retained_site.get("longitude"):
        reasons.append("site_location_changed")
    return reasons


@transaction.atomic
def approve_terrain_analysis(
    analysis: TerrainAnalysis,
    *,
    actor,
) -> TerrainAnalysis:
    analysis = TerrainAnalysis.objects.select_for_update().get(pk=analysis.pk)
    if analysis.status == TerrainAnalysis.Status.APPROVED:
        raise ValidationError("The terrain analysis is already approved.")
    if analysis.job_state != TerrainAnalysis.JobState.COMPLETE:
        raise ValidationError("Only completed terrain evidence can be approved.")
    if analysis.analysis_state != TerrainAnalysis.AnalysisState.COMPLETE:
        raise ValidationError(
            "Only complete terrain evidence without gaps or unsupported conditions can be approved."
        )
    reasons = terrain_stale_reasons(analysis)
    if reasons:
        raise ValidationError(
            {
                "detail": "The terrain evidence is stale and cannot be approved.",
                "stale_reasons": reasons,
            }
        )
    analysis.status = TerrainAnalysis.Status.APPROVED
    analysis.approved_by = actor
    analysis.approved_at = timezone.now()
    analysis.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    return analysis
