from __future__ import annotations

import math
from collections import Counter
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .coverage import DISCLAIMER, canonical_digest
from .models import (
    CalibrationSet,
    CalibrationSetObservation,
    DirectionalCoverageAnalysis,
    FieldObservation,
    FieldObservationReview,
)

CALIBRATION_ALGORITHM = "observation-envelope"
CALIBRATION_ALGORITHM_VERSION = "observation-envelope-v1-provisional"
CALIBRATION_DISCLAIMER = (
    f"{DISCLAIMER} Local calibration is incident-specific decision support. "
    "It is never promoted to an organization default automatically."
)
ALLOWED_QUALITY_FLAGS = {
    "equipment_uncertain",
    "interference_observed",
    "location_uncertain",
    "missing_measurement",
    "multipath_suspected",
    "obstruction_observed",
    "outlier_candidate",
    "weather_effect",
}
ALLOWED_ENVIRONMENT_KEYS = {
    "mobility",
    "structures",
    "terrain",
    "vegetation",
    "weather",
}
ALLOWED_MEASUREMENTS = {
    "measured_distance_m": (Decimal("0.001"), Decimal("1000000")),
    "predicted_distance_m": (Decimal("0.001"), Decimal("1000000")),
    "rssi_dbm": (Decimal("-300"), Decimal("100")),
    "signal_quality_percent": (Decimal("0"), Decimal("100")),
}


def calibration_status() -> dict[str, Any]:
    approved_methods = getattr(settings, "ICT_APPROVED_CALIBRATION_METHODS", [])
    return {
        "algorithm": CALIBRATION_ALGORITHM,
        "algorithm_version": CALIBRATION_ALGORITHM_VERSION,
        "approved_for_operational_use": CALIBRATION_ALGORITHM_VERSION in approved_methods,
        "minimum_usable_observations": 3,
        "ratio_bounds": {"minimum": "0.250", "maximum": "4.000"},
        "location_rule": (
            "Generalized coordinates are rounded before persistence; redacted coordinates "
            "are discarded before persistence."
        ),
        "promotion_rule": (
            "A calibrated recommendation remains incident-local and is never promoted or "
            "written over an organization default automatically."
        ),
        "disclaimer": CALIBRATION_DISCLAIMER,
    }


def _decimal(value: Any, *, field: str, minimum: Decimal, maximum: Decimal) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError({field: "Enter a valid decimal value."}) from exc
    if not result.is_finite() or result < minimum or result > maximum:
        raise ValidationError(
            {field: f"Value must be between {format(minimum, 'f')} and {format(maximum, 'f')}."}
        )
    return result


def _normalize_measurements(values: Any) -> dict[str, str]:
    if not isinstance(values, dict):
        raise ValidationError({"measurements": "Measurements must be an object."})
    unknown = sorted(set(values) - set(ALLOWED_MEASUREMENTS))
    if unknown:
        raise ValidationError(
            {"measurements": f"Unsupported measurement fields: {', '.join(unknown)}."}
        )
    normalized: dict[str, str] = {}
    for field, value in values.items():
        minimum, maximum = ALLOWED_MEASUREMENTS[field]
        normalized[field] = format(
            _decimal(value, field=field, minimum=minimum, maximum=maximum),
            "f",
        )
    return normalized


def _normalize_environment(values: Any) -> dict[str, str]:
    if not isinstance(values, dict):
        raise ValidationError({"environment": "Environment must be an object."})
    unknown = sorted(set(values) - ALLOWED_ENVIRONMENT_KEYS)
    if unknown:
        raise ValidationError(
            {"environment": f"Unsupported environment fields: {', '.join(unknown)}."}
        )
    normalized = {}
    for key, value in values.items():
        text = str(value).strip()
        if not text or len(text) > 80:
            raise ValidationError(
                {"environment": f"{key} must contain 1 to 80 visible characters."}
            )
        normalized[key] = text
    return normalized


def _normalize_quality_flags(values: Any) -> list[str]:
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        raise ValidationError({"quality_flags": "Quality flags must be a list of strings."})
    flags = sorted(set(values))
    unknown = sorted(set(flags) - ALLOWED_QUALITY_FLAGS)
    if unknown:
        raise ValidationError(
            {"quality_flags": f"Unsupported quality flags: {', '.join(unknown)}."}
        )
    return flags


def _generalize_coordinates(
    latitude: Decimal,
    longitude: Decimal,
    precision_m: int,
) -> tuple[Decimal, Decimal]:
    latitude_float = float(latitude)
    latitude_step = precision_m / 111_320
    longitude_scale = max(abs(math.cos(math.radians(latitude_float))), 0.01)
    longitude_step = precision_m / (111_320 * longitude_scale)
    generalized_latitude = round(latitude_float / latitude_step) * latitude_step
    generalized_longitude = round(float(longitude) / longitude_step) * longitude_step
    return (
        Decimal(str(max(-90, min(90, generalized_latitude)))).quantize(
            Decimal("0.000001"),
            rounding=ROUND_HALF_UP,
        ),
        Decimal(str(max(-180, min(180, generalized_longitude)))).quantize(
            Decimal("0.000001"),
            rounding=ROUND_HALF_UP,
        ),
    )


def _sanitize_location(
    *,
    precision: str,
    latitude: Any,
    longitude: Any,
    precision_m: Any,
) -> tuple[Decimal | None, Decimal | None, int | None]:
    if precision == FieldObservation.LocationPrecision.REDACTED:
        return None, None, None
    if latitude is None or longitude is None:
        raise ValidationError(
            {"location": "Exact and generalized observations require both coordinates."}
        )
    latitude_value = _decimal(
        latitude,
        field="latitude",
        minimum=Decimal("-90"),
        maximum=Decimal("90"),
    )
    longitude_value = _decimal(
        longitude,
        field="longitude",
        minimum=Decimal("-180"),
        maximum=Decimal("180"),
    )
    try:
        precision_value = int(precision_m)
    except (TypeError, ValueError) as exc:
        raise ValidationError({"location_precision_m": "Enter a whole number of meters."}) from exc
    if precision_value < 1 or precision_value > 1_000_000:
        raise ValidationError(
            {"location_precision_m": "Location precision must be 1 to 1,000,000 meters."}
        )
    if precision == FieldObservation.LocationPrecision.GENERALIZED:
        if precision_value < 100:
            raise ValidationError(
                {
                    "location_precision_m": (
                        "Generalized locations must use a precision of at least 100 meters."
                    )
                }
            )
        return (
            *_generalize_coordinates(latitude_value, longitude_value, precision_value),
            precision_value,
        )
    return (
        latitude_value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP),
        longitude_value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP),
        precision_value,
    )


def _validate_sources(values: dict[str, Any]) -> None:
    incident = values["incident"]
    infrastructure = values["infrastructure_rf_input_snapshot"]
    subscriber = values["subscriber_rf_input_snapshot"]
    if incident.archived_at is not None:
        raise ValidationError({"incident": "Archived incidents cannot accept observations."})
    for field, snapshot in (
        ("infrastructure_rf_input_snapshot", infrastructure),
        ("subscriber_rf_input_snapshot", subscriber),
    ):
        if snapshot.incident_id != incident.id:
            raise ValidationError({field: "The RF input snapshot belongs to another incident."})
        if snapshot.archived_at is not None:
            raise ValidationError({field: "Archived RF input snapshots cannot be observed."})
    if infrastructure.id == subscriber.id:
        raise ValidationError(
            {
                "subscriber_rf_input_snapshot": (
                    "Select distinct infrastructure and subscriber RF input snapshots."
                )
            }
        )

    coverage = values.get("coverage_estimate")
    if coverage:
        if coverage.incident_id != incident.id:
            raise ValidationError(
                {"coverage_estimate": "The estimate belongs to another incident."}
            )
        if coverage.status != coverage.Status.APPROVED:
            raise ValidationError({"coverage_estimate": "Approve the estimate before observation."})
        if coverage.rf_input_snapshot_id != infrastructure.id:
            raise ValidationError(
                {
                    "coverage_estimate": (
                        "The estimate does not use the selected infrastructure RF snapshot."
                    )
                }
            )

    directional = values.get("directional_analysis")
    if directional:
        if directional.incident_id != incident.id:
            raise ValidationError(
                {"directional_analysis": "The analysis belongs to another incident."}
            )
        if directional.status != DirectionalCoverageAnalysis.Status.APPROVED:
            raise ValidationError(
                {"directional_analysis": "Approve the directional analysis before observation."}
            )
        if (
            directional.infrastructure_rf_input_snapshot_id != infrastructure.id
            or directional.subscriber_rf_input_snapshot_id != subscriber.id
        ):
            raise ValidationError(
                {
                    "directional_analysis": (
                        "The analysis does not use the selected infrastructure and subscriber "
                        "RF snapshots."
                    )
                }
            )

    if values["evidence_type"] == FieldObservation.EvidenceType.MODELED and not (
        coverage or directional
    ):
        raise ValidationError(
            {
                "evidence_type": (
                    "Modeled observations require an approved coverage or directional analysis."
                )
            }
        )
    if (
        values["evidence_type"] == FieldObservation.EvidenceType.IMPORTED
        and not values.get("source_record_id", "").strip()
    ):
        raise ValidationError(
            {"source_record_id": "Imported observations require a source record identifier."}
        )


@transaction.atomic
def create_field_observation(*, values: dict[str, Any], actor) -> FieldObservation:
    values = dict(values)
    _validate_sources(values)
    if values["observed_to"] < values["observed_from"]:
        raise ValidationError({"observed_to": "Observation end cannot precede its start."})

    supersedes = values.get("supersedes")
    if supersedes:
        supersedes = (
            FieldObservation.objects.select_for_update()
            .select_related("incident")
            .get(pk=supersedes.pk)
        )
        if supersedes.incident_id != values["incident"].id:
            raise ValidationError({"supersedes": "Corrections cannot cross incident boundaries."})
        if hasattr(supersedes, "superseded_by"):
            raise ValidationError({"supersedes": "That observation already has a correction."})

    latitude, longitude, precision_m = _sanitize_location(
        precision=values["location_precision"],
        latitude=values.get("latitude"),
        longitude=values.get("longitude"),
        precision_m=values.get("location_precision_m"),
    )
    measurements = _normalize_measurements(values.get("measurements", {}))
    environment = _normalize_environment(values.get("environment", {}))
    quality_flags = _normalize_quality_flags(values.get("quality_flags", []))
    notes = values.get("notes", "").strip()
    if len(notes) > 2_000:
        raise ValidationError({"notes": "Notes are limited to 2,000 characters."})
    observer_source = values["observer_source"].strip()
    collection_method = values["collection_method"].strip()
    source_revision = values["source_revision"].strip()
    if not observer_source or not collection_method or not source_revision:
        raise ValidationError(
            "Observer/source, collection method, and source revision are required."
        )

    infrastructure = values["infrastructure_rf_input_snapshot"]
    subscriber = values["subscriber_rf_input_snapshot"]
    coverage = values.get("coverage_estimate")
    directional = values.get("directional_analysis")
    input_snapshot = {
        "schema_version": "field-observation-input-v1",
        "incident_id": str(values["incident"].id),
        "classification": values["classification"],
        "evidence_type": values["evidence_type"],
        "time_window": {
            "from": values["observed_from"].isoformat(),
            "to": values["observed_to"].isoformat(),
        },
        "location": {
            "precision": values["location_precision"],
            "coordinate_reference": "EPSG:4326",
            "latitude": format(latitude, "f") if latitude is not None else None,
            "longitude": format(longitude, "f") if longitude is not None else None,
            "precision_m": precision_m,
            "raw_coordinates_retained": values["location_precision"]
            == FieldObservation.LocationPrecision.EXACT,
        },
        "path": {
            "direction_degrees": (
                format(values["direction_degrees"], "f")
                if values.get("direction_degrees") is not None
                else None
            ),
            "distance_m": values.get("path_distance_m"),
        },
        "rf_inputs": {
            "infrastructure": {
                "id": str(infrastructure.id),
                "input_sha256": infrastructure.input_sha256,
            },
            "subscriber": {
                "id": str(subscriber.id),
                "input_sha256": subscriber.input_sha256,
            },
        },
        "analysis_evidence": {
            "coverage_estimate": (
                {
                    "id": str(coverage.id),
                    "result_sha256": coverage.result_sha256,
                }
                if coverage
                else None
            ),
            "directional_analysis": (
                {
                    "id": str(directional.id),
                    "result_sha256": directional.result_sha256,
                }
                if directional
                else None
            ),
        },
        "observer_source": observer_source,
        "collection_method": collection_method,
        "environment": environment,
        "measurements": measurements,
        "notes": notes,
        "quality_flags": quality_flags,
        "source_record_id": values.get("source_record_id", "").strip(),
        "source_revision": source_revision,
        "supersedes_id": str(supersedes.id) if supersedes else None,
    }
    return FieldObservation.objects.create(
        incident=values["incident"],
        infrastructure_rf_input_snapshot=infrastructure,
        subscriber_rf_input_snapshot=subscriber,
        coverage_estimate=coverage,
        directional_analysis=directional,
        supersedes=supersedes,
        classification=values["classification"],
        evidence_type=values["evidence_type"],
        observed_from=values["observed_from"],
        observed_to=values["observed_to"],
        location_precision=values["location_precision"],
        coordinate_reference="EPSG:4326",
        latitude=latitude,
        longitude=longitude,
        location_precision_m=precision_m,
        direction_degrees=values.get("direction_degrees"),
        path_distance_m=values.get("path_distance_m"),
        observer_source=observer_source,
        collection_method=collection_method,
        environment=environment,
        measurements=measurements,
        notes=notes,
        quality_flags=quality_flags,
        source_record_id=values.get("source_record_id", "").strip(),
        source_revision=source_revision,
        input_snapshot=input_snapshot,
        input_sha256=canonical_digest(input_snapshot),
        created_by=actor,
    )


@transaction.atomic
def review_field_observation(
    observation: FieldObservation,
    *,
    decision: str,
    reason: str,
    actor,
) -> FieldObservationReview:
    observation = (
        FieldObservation.objects.select_for_update()
        .select_related("incident")
        .get(pk=observation.pk)
    )
    reason = reason.strip()
    if not reason or len(reason) > 1_000:
        raise ValidationError({"reason": "A review reason of 1 to 1,000 characters is required."})
    if decision == FieldObservationReview.Decision.APPROVED and hasattr(
        observation, "superseded_by"
    ):
        raise ValidationError("A superseded observation cannot be approved.")
    previous = observation.reviews.order_by("-created_at", "-id").first()
    if previous and previous.decision == decision:
        raise ValidationError(f"The observation is already {decision}.")
    evidence = {
        "schema_version": "field-observation-review-v1",
        "observation_id": str(observation.id),
        "observation_sha256": observation.input_sha256,
        "decision": decision,
        "reason": reason,
        "reviewed_by_id": str(actor.id),
        "previous_review_sha256": previous.evidence_sha256 if previous else None,
    }
    return FieldObservationReview.objects.create(
        observation=observation,
        decision=decision,
        reason=reason,
        evidence_sha256=canonical_digest(evidence),
        reviewed_by=actor,
    )


def _measurement_pair(observation: FieldObservation) -> tuple[Decimal, Decimal] | None:
    try:
        measured = Decimal(str(observation.measurements["measured_distance_m"]))
        predicted = Decimal(str(observation.measurements["predicted_distance_m"]))
    except (KeyError, InvalidOperation, TypeError, ValueError):
        return None
    if not measured.is_finite() or not predicted.is_finite() or measured <= 0 or predicted <= 0:
        return None
    return measured, predicted


def _mean(values: list[Decimal]) -> Decimal:
    return sum(values, Decimal("0")) / Decimal(len(values))


def _median(values: list[Decimal]) -> Decimal:
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / Decimal("2")


@transaction.atomic
def create_calibration_set(
    *,
    incident,
    name: str,
    observations: list[FieldObservation],
    baseline_preset: str,
    baseline_preset_version: str,
    parameters: dict[str, Any],
    actor,
) -> CalibrationSet:
    if incident.archived_at is not None:
        raise ValidationError({"incident": "Archived incidents cannot be calibrated."})
    name = name.strip()
    baseline_preset = baseline_preset.strip()
    baseline_preset_version = baseline_preset_version.strip()
    if not name or not baseline_preset or not baseline_preset_version:
        raise ValidationError("Name, baseline preset, and baseline preset version are required.")
    if not observations or len(observations) > 500:
        raise ValidationError({"observations": "Select 1 to 500 approved observations."})
    if len({observation.id for observation in observations}) != len(observations):
        raise ValidationError({"observations": "Each observation may be selected once."})

    allowed_parameter_keys = {"maximum_ratio", "minimum_ratio", "minimum_samples"}
    if not isinstance(parameters, dict) or set(parameters) - allowed_parameter_keys:
        raise ValidationError(
            {
                "parameters": (
                    "Only minimum_samples, minimum_ratio, and maximum_ratio are supported."
                )
            }
        )
    try:
        minimum_samples = int(parameters.get("minimum_samples", 3))
    except (TypeError, ValueError) as exc:
        raise ValidationError({"parameters": "minimum_samples must be a whole number."}) from exc
    if minimum_samples < 3 or minimum_samples > 100:
        raise ValidationError({"parameters": "minimum_samples must be between 3 and 100."})
    minimum_ratio = _decimal(
        parameters.get("minimum_ratio", "0.25"),
        field="minimum_ratio",
        minimum=Decimal("0.01"),
        maximum=Decimal("1"),
    )
    maximum_ratio = _decimal(
        parameters.get("maximum_ratio", "4"),
        field="maximum_ratio",
        minimum=Decimal("1"),
        maximum=Decimal("10"),
    )
    if maximum_ratio <= minimum_ratio:
        raise ValidationError({"parameters": "maximum_ratio must exceed minimum_ratio."})
    normalized_parameters = {
        "minimum_samples": minimum_samples,
        "minimum_ratio": format(minimum_ratio, "f"),
        "maximum_ratio": format(maximum_ratio, "f"),
        "rounding": "0.001",
    }

    locked_observations = list(
        FieldObservation.objects.select_for_update()
        .select_related(
            "incident",
            "infrastructure_rf_input_snapshot",
            "subscriber_rf_input_snapshot",
        )
        .prefetch_related("reviews")
        .filter(pk__in=[observation.pk for observation in observations])
    )
    if len(locked_observations) != len(observations):
        raise ValidationError({"observations": "One or more observations no longer exist."})
    locked_observations.sort(key=lambda observation: str(observation.id))

    observation_snapshot = []
    ratios: list[Decimal] = []
    measured_pairs: list[tuple[Decimal, Decimal]] = []
    exclusions = []
    review_digests: dict[Any, str] = {}
    for observation in locked_observations:
        if observation.incident_id != incident.id:
            raise ValidationError({"observations": "Observations cannot cross incidents."})
        if hasattr(observation, "superseded_by"):
            raise ValidationError(
                {"observations": f"Observation {observation.id} has been superseded."}
            )
        review = observation.reviews.order_by("-created_at", "-id").first()
        if not review or review.decision != FieldObservationReview.Decision.APPROVED:
            raise ValidationError(
                {"observations": f"Observation {observation.id} is not currently approved."}
            )
        review_digests[observation.id] = review.evidence_sha256
        pair = _measurement_pair(observation)
        ratio = None
        exclusion = None
        if pair is None:
            exclusion = {
                "observation_id": str(observation.id),
                "code": "missing_distance_pair",
                "reason": (
                    "Both measured_distance_m and predicted_distance_m are required for fitting."
                ),
            }
        else:
            measured, predicted = pair
            candidate = measured / predicted
            if candidate < minimum_ratio or candidate > maximum_ratio:
                exclusion = {
                    "observation_id": str(observation.id),
                    "code": "ratio_outlier",
                    "reason": (
                        "The measured-to-predicted ratio is outside the declared fitting bounds."
                    ),
                }
            else:
                ratio = candidate
                ratios.append(candidate)
                measured_pairs.append(pair)
        if exclusion:
            exclusions.append(exclusion)
        observation_snapshot.append(
            {
                "id": str(observation.id),
                "classification": observation.classification,
                "evidence_type": observation.evidence_type,
                "observation_sha256": observation.input_sha256,
                "review_evidence_sha256": review.evidence_sha256,
                "measured_distance_m": (format(pair[0], "f") if pair is not None else None),
                "predicted_distance_m": (format(pair[1], "f") if pair is not None else None),
                "fitting_ratio": format(ratio, "f") if ratio is not None else None,
                "included_in_fit": ratio is not None,
            }
        )

    classification_counts = dict(
        sorted(Counter(observation.classification for observation in locked_observations).items())
    )
    warnings = []
    if exclusions:
        warnings.append(f"{len(exclusions)} selected observations were excluded from fitting.")
    calculation_state = (
        CalibrationSet.CalculationState.COMPLETE
        if len(ratios) >= minimum_samples
        else CalibrationSet.CalculationState.INSUFFICIENT_DATA
    )
    if calculation_state == CalibrationSet.CalculationState.COMPLETE:
        multiplier = _median(ratios).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        before_errors = [abs(measured - predicted) for measured, predicted in measured_pairs]
        after_errors = [
            abs(measured - (predicted * multiplier)) for measured, predicted in measured_pairs
        ]
        before_percent = [
            (abs(measured - predicted) / measured) * Decimal("100")
            for measured, predicted in measured_pairs
        ]
        after_percent = [
            (abs(measured - (predicted * multiplier)) / measured) * Decimal("100")
            for measured, predicted in measured_pairs
        ]
        before_after = {
            "before": {
                "mean_absolute_error_m": format(
                    _mean(before_errors).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP),
                    "f",
                ),
                "mean_absolute_percentage_error": format(
                    _mean(before_percent).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP),
                    "f",
                ),
            },
            "after": {
                "mean_absolute_error_m": format(
                    _mean(after_errors).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP),
                    "f",
                ),
                "mean_absolute_percentage_error": format(
                    _mean(after_percent).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP),
                    "f",
                ),
            },
        }
    else:
        multiplier = None
        before_after = {"before": None, "after": None}
        warnings.append(
            f"At least {minimum_samples} usable distance pairs are required; {len(ratios)} remain."
        )

    recommended_preset = {
        "schema_version": "incident-local-calibration-recommendation-v1",
        "base_preset": baseline_preset,
        "base_preset_version": baseline_preset_version,
        "distance_multiplier": format(multiplier, "f") if multiplier is not None else None,
        "scope": "incident_local",
        "promotion_state": "not_promoted",
        "organization_default_overwritten": False,
    }
    observation_sha256 = canonical_digest(observation_snapshot)
    result_snapshot = {
        "schema_version": "calibration-result-v1",
        "calculation_state": calculation_state,
        "algorithm": CALIBRATION_ALGORITHM,
        "algorithm_version": CALIBRATION_ALGORITHM_VERSION,
        "parameters": normalized_parameters,
        "classification_counts": classification_counts,
        "selected_observation_count": len(locked_observations),
        "usable_observation_count": len(ratios),
        "observation_sha256": observation_sha256,
        "recommended_preset": recommended_preset,
        "before_after": before_after,
        "warnings": warnings,
        "exclusions": exclusions,
        "disclaimer": CALIBRATION_DISCLAIMER,
    }
    current_version = (
        CalibrationSet.objects.select_for_update()
        .filter(incident=incident, name=name)
        .aggregate(maximum=Max("version"))["maximum"]
        or 0
    )
    calibration_set = CalibrationSet.objects.create(
        incident=incident,
        name=name,
        version=current_version + 1,
        calculation_state=calculation_state,
        algorithm=CALIBRATION_ALGORITHM,
        algorithm_version=CALIBRATION_ALGORITHM_VERSION,
        parameters=normalized_parameters,
        baseline_preset=baseline_preset,
        baseline_preset_version=baseline_preset_version,
        observation_snapshot=observation_snapshot,
        observation_sha256=observation_sha256,
        recommended_preset=recommended_preset,
        before_after=before_after,
        warnings=warnings,
        exclusions=exclusions,
        result_snapshot=result_snapshot,
        result_sha256=canonical_digest(result_snapshot),
        created_by=actor,
    )
    CalibrationSetObservation.objects.bulk_create(
        [
            CalibrationSetObservation(
                calibration_set=calibration_set,
                observation=observation,
                observation_sha256=observation.input_sha256,
                review_evidence_sha256=review_digests[observation.id],
                position=position,
            )
            for position, observation in enumerate(locked_observations, start=1)
        ]
    )
    return calibration_set


@transaction.atomic
def approve_calibration_set(calibration_set: CalibrationSet, *, actor) -> CalibrationSet:
    calibration_set = (
        CalibrationSet.objects.select_for_update()
        .prefetch_related("observation_links__observation__reviews")
        .get(pk=calibration_set.pk)
    )
    if calibration_set.status == CalibrationSet.Status.APPROVED:
        raise ValidationError("The calibration set is already approved.")
    if calibration_set.calculation_state != CalibrationSet.CalculationState.COMPLETE:
        raise ValidationError("Only a complete calibration set can be approved.")
    if calibration_set.algorithm_version not in getattr(
        settings, "ICT_APPROVED_CALIBRATION_METHODS", []
    ):
        raise ValidationError(
            "The exact calibration method has not passed the configured RF/privacy gate."
        )
    for link in calibration_set.observation_links.all():
        observation = link.observation
        if hasattr(observation, "superseded_by"):
            raise ValidationError(f"Observation {observation.id} was superseded after calibration.")
        review = observation.reviews.order_by("-created_at", "-id").first()
        if (
            not review
            or review.decision != FieldObservationReview.Decision.APPROVED
            or review.evidence_sha256 != link.review_evidence_sha256
            or observation.input_sha256 != link.observation_sha256
        ):
            raise ValidationError(
                f"Observation {observation.id} review evidence changed after calibration."
            )
    CalibrationSet.objects.filter(pk=calibration_set.pk).update(
        status=CalibrationSet.Status.APPROVED,
        approved_by=actor,
        approved_at=timezone.now(),
    )
    return CalibrationSet.objects.get(pk=calibration_set.pk)
