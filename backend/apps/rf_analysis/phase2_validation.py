from __future__ import annotations

import hashlib
import json
import logging
from decimal import Decimal, InvalidOperation
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.plans.models import PlanRevision

from .coverage import DISCLAIMER, canonical_digest
from .models import (
    CalibrationSet,
    CoverageEstimate,
    DirectionalCoverageAnalysis,
    FieldObservationReview,
    HAATCalculation,
    Phase2ValidationBundle,
)

VALIDATION_PROFILE_ID = "phase-2-validation"
VALIDATION_PROFILE_VERSION = "phase-2-validation-v1-provisional"
VALIDATION_METHOD_VERSION = "deterministic-distance-ratio-comparison-v1-provisional"
EXPORT_SCHEMA_VERSION = "phase-2-validation-evidence-export-v1"
NON_PRODUCTION_LABEL = "NON-PRODUCTION PHASE 2 VALIDATION EVIDENCE"
VALIDATION_DISCLAIMER = (
    f"{DISCLAIMER} This evidence checks deterministic software behavior and provenance. "
    "It is not field validation, scientific validation, spectrum authorization, or approval "
    "for operational use."
)
MAX_VALIDATION_ASSIGNMENTS = 1_000
MAX_VALIDATION_OBSERVATIONS = 1_000

logger = logging.getLogger(__name__)


def validation_status() -> dict[str, Any]:
    approved_profiles = getattr(settings, "ICT_APPROVED_PHASE2_VALIDATION_PROFILES", [])
    return {
        "validation_profile_id": VALIDATION_PROFILE_ID,
        "validation_profile_version": VALIDATION_PROFILE_VERSION,
        "validation_method_version": VALIDATION_METHOD_VERSION,
        "approved_for_release_candidate_use": VALIDATION_PROFILE_VERSION in approved_profiles,
        "execution_model": "explicit synchronous staged job",
        "cancellation_boundary": (
            "Queued work can be cancelled before execution. Once the explicit run request "
            "starts, the request must finish; no background worker is configured."
        ),
        "classification": NON_PRODUCTION_LABEL,
        "resource_safety_limits": {
            "maximum_plan_assignments": MAX_VALIDATION_ASSIGNMENTS,
            "maximum_calibration_observations": MAX_VALIDATION_OBSERVATIONS,
            "maximum_verification_upload_bytes": 10 * 1024 * 1024,
        },
        "disclaimer": VALIDATION_DISCLAIMER,
    }


def _plan_snapshot(revision: PlanRevision) -> dict[str, Any]:
    def minimized_site_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
        return {
            key: snapshot.get(key)
            for key in (
                "site_id",
                "name",
                "latitude",
                "longitude",
                "coordinate_format",
                "source_identity",
                "source_retrieved_at",
                "rings",
            )
        }

    assignments = []
    for assignment in revision.assignments.order_by("position", "id"):
        site_snapshots = [
            minimized_site_snapshot(link.site_snapshot)
            for link in assignment.site_links.order_by("site_id", "id")
            if link.site_snapshot
        ]
        assignments.append(
            {
                "id": str(assignment.id),
                "position": assignment.position,
                "function": assignment.function,
                "channel_name": assignment.channel_name,
                "assignment": assignment.assignment,
                "resource_snapshot": assignment.resource_snapshot,
                "operating_classification": assignment.operating_classification,
                "technology_subtype": assignment.technology_subtype,
                "subscriber_profile_version_id": (
                    str(assignment.subscriber_profile_version_id)
                    if assignment.subscriber_profile_version_id
                    else None
                ),
                "rx_frequency_hz": assignment.rx_frequency_hz,
                "rx_squelch": assignment.rx_squelch,
                "tx_frequency_hz": assignment.tx_frequency_hz,
                "tx_squelch": assignment.tx_squelch,
                "mode": assignment.mode,
                "structured_note": assignment.structured_note,
                "site_snapshots": site_snapshots,
            }
        )
    relationships = []
    for relationship in revision.relationships.prefetch_related("assignments").order_by("id"):
        relationships.append(
            {
                "id": str(relationship.id),
                "relationship_type": relationship.relationship_type,
                "label": relationship.label,
                "assignment_ids": sorted(
                    str(assignment_id)
                    for assignment_id in relationship.assignments.values_list("id", flat=True)
                ),
            }
        )
    content = {
        "revision_id": str(revision.id),
        "revision_number": revision.number,
        "status": revision.status,
        "approved_by_id": str(revision.approved_by_id),
        "approved_at": revision.approved_at.isoformat() if revision.approved_at else None,
        "operational_period_id": str(revision.plan.operational_period_id),
        "assignments": assignments,
        "relationships": relationships,
        "excluded_fields": [
            "contact_name",
            "site_address",
            "phone_numbers",
            "contact_24_hour",
            "remarks",
            "site_address",
            "site_description",
            "site_entered_coordinate",
        ],
    }
    return {**content, "content_sha256": canonical_digest(content)}


def _source_reference(source, *, digest_fields: tuple[str, ...]) -> dict[str, Any]:
    return {
        "id": str(source.id),
        "status": source.status,
        "approved_by_id": str(source.approved_by_id),
        "approved_at": source.approved_at.isoformat() if source.approved_at else None,
        **{field: getattr(source, field) for field in digest_fields},
    }


def _validate_source_chain(
    *,
    incident,
    approved_revision,
    haat_calculation,
    coverage_estimate,
    directional_analysis,
    calibration_set,
) -> None:
    sources = (
        approved_revision.plan.incident,
        haat_calculation.incident,
        coverage_estimate.incident,
        directional_analysis.incident,
        calibration_set.incident,
    )
    if any(source_incident.id != incident.id for source_incident in sources):
        raise ValidationError("Every Phase 2 validation source must belong to the incident.")
    if approved_revision.status != PlanRevision.Status.APPROVED:
        raise ValidationError({"approved_revision": "Select an approved plan revision."})
    if approved_revision.assignments.count() > MAX_VALIDATION_ASSIGNMENTS:
        raise ValidationError(
            {
                "approved_revision": (
                    f"Phase 2 validation is limited to {MAX_VALIDATION_ASSIGNMENTS} plan "
                    "assignments per bundle."
                )
            }
        )
    if haat_calculation.status != HAATCalculation.Status.APPROVED:
        raise ValidationError({"haat_calculation": "Select an approved HAAT calculation."})
    if haat_calculation.calculation_state != HAATCalculation.CalculationState.COMPLETE:
        raise ValidationError({"haat_calculation": "The HAAT calculation must be complete."})
    if coverage_estimate.status != CoverageEstimate.Status.APPROVED:
        raise ValidationError({"coverage_estimate": "Select an approved coverage estimate."})
    if coverage_estimate.calculation_state != CoverageEstimate.CalculationState.COMPLETE:
        raise ValidationError({"coverage_estimate": "The coverage estimate must be complete."})
    if directional_analysis.status != DirectionalCoverageAnalysis.Status.APPROVED:
        raise ValidationError({"directional_analysis": "Select an approved directional analysis."})
    if directional_analysis.calculation_state != (
        DirectionalCoverageAnalysis.CalculationState.COMPLETE
    ):
        raise ValidationError(
            {"directional_analysis": "The directional analysis must be complete."}
        )
    if calibration_set.status != CalibrationSet.Status.APPROVED:
        raise ValidationError({"calibration_set": "Select an approved calibration set."})
    if calibration_set.calculation_state != CalibrationSet.CalculationState.COMPLETE:
        raise ValidationError({"calibration_set": "The calibration set must be complete."})
    if calibration_set.observation_links.count() > MAX_VALIDATION_OBSERVATIONS:
        raise ValidationError(
            {
                "calibration_set": (
                    f"Phase 2 validation is limited to {MAX_VALIDATION_OBSERVATIONS} "
                    "calibration observations per bundle."
                )
            }
        )
    if haat_calculation.elevation_snapshot.current_state == "stale":
        raise ValidationError({"haat_calculation": "The selected elevation snapshot is stale."})
    if coverage_estimate.haat_calculation_id != haat_calculation.id:
        raise ValidationError(
            {"coverage_estimate": "The coverage estimate must use the selected HAAT calculation."}
        )
    if directional_analysis.haat_calculation_id != haat_calculation.id:
        raise ValidationError(
            {
                "directional_analysis": (
                    "The directional analysis must use the selected HAAT calculation."
                )
            }
        )
    if coverage_estimate.rf_input_snapshot_id != haat_calculation.rf_input_snapshot_id:
        raise ValidationError(
            {"coverage_estimate": "The coverage and HAAT RF input snapshots do not match."}
        )
    if (
        directional_analysis.infrastructure_rf_input_snapshot_id
        != haat_calculation.rf_input_snapshot_id
    ):
        raise ValidationError(
            {"directional_analysis": "The directional infrastructure input does not match HAAT."}
        )
    for link in calibration_set.observation_links.select_related("observation"):
        observation = link.observation
        if observation.infrastructure_rf_input_snapshot_id != (
            directional_analysis.infrastructure_rf_input_snapshot_id
        ) or observation.subscriber_rf_input_snapshot_id != (
            directional_analysis.subscriber_rf_input_snapshot_id
        ):
            raise ValidationError(
                {
                    "calibration_set": (
                        "Every calibration observation must use the selected directional RF "
                        "input pair."
                    )
                }
            )
        review = observation.reviews.order_by("-created_at", "-id").first()
        if (
            hasattr(observation, "superseded_by")
            or not review
            or review.decision != FieldObservationReview.Decision.APPROVED
            or review.evidence_sha256 != link.review_evidence_sha256
            or observation.input_sha256 != link.observation_sha256
        ):
            raise ValidationError(
                {
                    "calibration_set": (
                        "Calibration observation review evidence changed after approval."
                    )
                }
            )
    digest_checks = (
        (haat_calculation.result_snapshot, haat_calculation.result_sha256, "haat_calculation"),
        (coverage_estimate.input_snapshot, coverage_estimate.input_sha256, "coverage_estimate"),
        (coverage_estimate.result_snapshot, coverage_estimate.result_sha256, "coverage_estimate"),
        (
            directional_analysis.input_snapshot,
            directional_analysis.input_sha256,
            "directional_analysis",
        ),
        (
            directional_analysis.result_snapshot,
            directional_analysis.result_sha256,
            "directional_analysis",
        ),
        (
            calibration_set.observation_snapshot,
            calibration_set.observation_sha256,
            "calibration_set",
        ),
        (calibration_set.result_snapshot, calibration_set.result_sha256, "calibration_set"),
    )
    for snapshot, expected_digest, field in digest_checks:
        if canonical_digest(snapshot) != expected_digest:
            raise ValidationError(
                {field: "The selected source snapshot does not match its retained digest."}
            )


def _input_snapshot(
    *,
    incident,
    approved_revision,
    haat_calculation,
    coverage_estimate,
    directional_analysis,
    calibration_set,
) -> dict[str, Any]:
    plan = _plan_snapshot(approved_revision)
    return {
        "schema_version": "phase-2-validation-input-v1",
        "classification": NON_PRODUCTION_LABEL,
        "incident_id": str(incident.id),
        "application_version": settings.APP_VERSION,
        "validation_profile": {
            "id": VALIDATION_PROFILE_ID,
            "version": VALIDATION_PROFILE_VERSION,
            "method_version": VALIDATION_METHOD_VERSION,
        },
        "approved_plan": plan,
        "sources": {
            "haat": _source_reference(
                haat_calculation,
                digest_fields=("result_sha256", "method_version"),
            ),
            "coverage": _source_reference(
                coverage_estimate,
                digest_fields=("input_sha256", "result_sha256", "engine_version", "preset_version"),
            ),
            "directional": _source_reference(
                directional_analysis,
                digest_fields=(
                    "input_sha256",
                    "result_sha256",
                    "engine_version",
                    "preset_version",
                    "rule_version",
                ),
            ),
            "calibration": _source_reference(
                calibration_set,
                digest_fields=(
                    "observation_sha256",
                    "result_sha256",
                    "algorithm_version",
                ),
            ),
        },
    }


@transaction.atomic
def queue_validation_bundle(
    *,
    incident,
    approved_revision,
    haat_calculation,
    coverage_estimate,
    directional_analysis,
    calibration_set,
    actor,
    supersedes=None,
) -> Phase2ValidationBundle:
    _validate_source_chain(
        incident=incident,
        approved_revision=approved_revision,
        haat_calculation=haat_calculation,
        coverage_estimate=coverage_estimate,
        directional_analysis=directional_analysis,
        calibration_set=calibration_set,
    )
    if supersedes and supersedes.incident_id != incident.id:
        raise ValidationError({"supersedes": "A retry must remain in the same incident."})
    snapshot = _input_snapshot(
        incident=incident,
        approved_revision=approved_revision,
        haat_calculation=haat_calculation,
        coverage_estimate=coverage_estimate,
        directional_analysis=directional_analysis,
        calibration_set=calibration_set,
    )
    return Phase2ValidationBundle.objects.create(
        incident=incident,
        approved_revision=approved_revision,
        haat_calculation=haat_calculation,
        coverage_estimate=coverage_estimate,
        directional_analysis=directional_analysis,
        calibration_set=calibration_set,
        supersedes=supersedes,
        validation_profile_id=VALIDATION_PROFILE_ID,
        validation_profile_version=VALIDATION_PROFILE_VERSION,
        app_version=settings.APP_VERSION,
        input_snapshot=snapshot,
        input_sha256=canonical_digest(snapshot),
        created_by=actor,
    )


def stale_reasons(bundle: Phase2ValidationBundle) -> list[str]:
    cached = getattr(bundle, "_phase2_stale_reasons_cache", None)
    if cached is not None:
        return cached
    if bundle.job_state != Phase2ValidationBundle.JobState.COMPLETE:
        return []
    reasons: list[str] = []
    if canonical_digest(bundle.input_snapshot) != bundle.input_sha256:
        reasons.append("bundle_input_digest_mismatch")
    if canonical_digest(bundle.result_snapshot) != bundle.result_sha256:
        reasons.append("bundle_result_digest_mismatch")
    if _plan_snapshot(bundle.approved_revision).get("content_sha256") != bundle.input_snapshot.get(
        "approved_plan", {}
    ).get("content_sha256"):
        reasons.append("approved_plan_changed")
    source_digest_checks = (
        (bundle.haat_calculation.result_snapshot, bundle.haat_calculation.result_sha256, "haat"),
        (
            bundle.coverage_estimate.input_snapshot,
            bundle.coverage_estimate.input_sha256,
            "coverage_input",
        ),
        (
            bundle.coverage_estimate.result_snapshot,
            bundle.coverage_estimate.result_sha256,
            "coverage_result",
        ),
        (
            bundle.directional_analysis.input_snapshot,
            bundle.directional_analysis.input_sha256,
            "directional_input",
        ),
        (
            bundle.directional_analysis.result_snapshot,
            bundle.directional_analysis.result_sha256,
            "directional_result",
        ),
        (
            bundle.calibration_set.observation_snapshot,
            bundle.calibration_set.observation_sha256,
            "calibration_observations",
        ),
        (
            bundle.calibration_set.result_snapshot,
            bundle.calibration_set.result_sha256,
            "calibration_result",
        ),
    )
    for snapshot, expected_digest, label in source_digest_checks:
        if canonical_digest(snapshot) != expected_digest:
            reasons.append(f"{label}_digest_mismatch")
    elevation = bundle.haat_calculation.elevation_snapshot
    if elevation.current_state == "stale":
        reasons.append("elevation_snapshot_stale")
    for link in bundle.calibration_set.observation_links.select_related(
        "observation"
    ).prefetch_related("observation__reviews"):
        observation = link.observation
        review = observation.reviews.order_by("-created_at", "-id").first()
        if hasattr(observation, "superseded_by"):
            reasons.append(f"observation_{observation.id}_superseded")
        elif (
            not review
            or review.decision != FieldObservationReview.Decision.APPROVED
            or review.evidence_sha256 != link.review_evidence_sha256
            or observation.input_sha256 != link.observation_sha256
        ):
            reasons.append(f"observation_{observation.id}_review_changed")
    result = sorted(set(reasons))
    bundle._phase2_stale_reasons_cache = result
    return result


def _distance_comparisons(calibration_set: CalibrationSet) -> tuple[list[dict[str, Any]], dict]:
    comparisons = []
    counts = {"within_tolerance": 0, "outside_tolerance": 0, "not_comparable": 0}
    for observation in calibration_set.observation_snapshot:
        measured = observation.get("measured_distance_m")
        predicted = observation.get("predicted_distance_m")
        verdict = "not_comparable"
        ratio = None
        delta_percent = None
        try:
            measured_decimal = Decimal(str(measured))
            predicted_decimal = Decimal(str(predicted))
            if measured_decimal > 0 and predicted_decimal > 0:
                ratio_decimal = measured_decimal / predicted_decimal
                ratio = format(ratio_decimal.quantize(Decimal("0.001")), "f")
                delta_percent = format(
                    ((ratio_decimal - Decimal("1")) * Decimal("100")).quantize(Decimal("0.1")),
                    "f",
                )
                verdict = (
                    "within_tolerance"
                    if Decimal("0.75") <= ratio_decimal <= Decimal("1.25")
                    else "outside_tolerance"
                )
        except (InvalidOperation, TypeError, ValueError, ZeroDivisionError):
            pass
        counts[verdict] += 1
        comparisons.append(
            {
                "observation_id": observation.get("id") or observation.get("observation_id"),
                "classification": observation.get("classification"),
                "evidence_type": observation.get("evidence_type"),
                "measured_distance_m": measured,
                "predicted_distance_m": predicted,
                "measured_to_predicted_ratio": ratio,
                "difference_percent": delta_percent,
                "verdict": verdict,
                "tolerance_rule": "0.750 <= measured/predicted <= 1.250",
            }
        )
    return comparisons, counts


def _result_snapshot(bundle: Phase2ValidationBundle) -> dict[str, Any]:
    haat = bundle.haat_calculation
    coverage = bundle.coverage_estimate
    directional = bundle.directional_analysis
    calibration = bundle.calibration_set
    comparisons, comparison_counts = _distance_comparisons(calibration)
    calibration_multiplier = calibration.recommended_preset.get("distance_multiplier")
    supported_conditions = [
        "approved_plan_revision",
        "approved_complete_haat",
        "approved_complete_band_environment_estimate",
        "approved_complete_directional_two_way_estimate",
        "approved_complete_incident_local_calibration",
        "deterministic_synthetic_distance_comparison",
    ]
    unsupported_conditions = [
        "field_or_scientific_validation",
        "coverage_guarantee",
        "propagation_study",
        "frequency_coordination_or_authorization",
        "automatic_organization_default_promotion",
        "mid_request_job_cancellation",
        "plan_assignment_to_rf_profile_traceability_not_yet_modeled",
    ]
    source_evidence = {
        "plan": bundle.input_snapshot["approved_plan"],
        "rf_inputs": {
            "infrastructure": {
                "id": str(directional.infrastructure_rf_input_snapshot_id),
                "snapshot": directional.infrastructure_rf_input_snapshot.input_snapshot,
                "input_sha256": directional.infrastructure_rf_input_snapshot.input_sha256,
            },
            "subscriber": {
                "id": str(directional.subscriber_rf_input_snapshot_id),
                "snapshot": directional.subscriber_rf_input_snapshot.input_snapshot,
                "input_sha256": directional.subscriber_rf_input_snapshot.input_sha256,
            },
        },
        "elevation": {
            "id": str(haat.elevation_snapshot_id),
            "provider": haat.elevation_snapshot.provider,
            "dataset_product": haat.elevation_snapshot.dataset_product,
            "source_version": haat.elevation_snapshot.source_version,
            "source_retrieved_at": (
                haat.elevation_snapshot.source_retrieved_at.isoformat()
                if haat.elevation_snapshot.source_retrieved_at
                else None
            ),
            "retrieved_at": haat.elevation_snapshot.retrieved_at.isoformat(),
            "query_snapshot": haat.elevation_snapshot.query_snapshot,
            "query_sha256": haat.elevation_snapshot.query_sha256,
            "sample_sha256": haat.elevation_snapshot.sample_sha256,
            "source_content_sha256": haat.elevation_snapshot.source_content_sha256,
            "transformation": haat.elevation_snapshot.transformation,
            "warnings": haat.elevation_snapshot.warnings,
            "stale_at": (
                haat.elevation_snapshot.stale_at.isoformat()
                if haat.elevation_snapshot.stale_at
                else None
            ),
        },
        "haat": {
            **_source_reference(haat, digest_fields=("result_sha256", "method_version")),
            "algorithm_snapshot": haat.algorithm_snapshot,
            "result_snapshot": haat.result_snapshot,
        },
        "coverage": {
            **_source_reference(
                coverage,
                digest_fields=("input_sha256", "result_sha256", "engine_version", "preset_version"),
            ),
            "model_snapshot": coverage.model_snapshot,
            "result_snapshot": coverage.result_snapshot,
        },
        "directional": {
            **_source_reference(
                directional,
                digest_fields=(
                    "input_sha256",
                    "result_sha256",
                    "engine_version",
                    "preset_version",
                    "rule_version",
                ),
            ),
            "model_snapshot": directional.model_snapshot,
            "result_snapshot": directional.result_snapshot,
        },
        "calibration": {
            **_source_reference(
                calibration,
                digest_fields=(
                    "observation_sha256",
                    "result_sha256",
                    "algorithm_version",
                ),
            ),
            "parameters": calibration.parameters,
            "observation_snapshot": calibration.observation_snapshot,
            "recommended_preset": calibration.recommended_preset,
            "before_after": calibration.before_after,
            "warnings": calibration.warnings,
            "exclusions": calibration.exclusions,
            "result_snapshot": calibration.result_snapshot,
        },
    }
    result = {
        "schema_version": "phase-2-validation-result-v1",
        "classification": NON_PRODUCTION_LABEL,
        "application_version": bundle.app_version,
        "validation_profile": {
            "id": bundle.validation_profile_id,
            "version": bundle.validation_profile_version,
            "method_version": VALIDATION_METHOD_VERSION,
        },
        "input_sha256": bundle.input_sha256,
        "confidence": {
            "level": "screening_only",
            "basis": (
                "Deterministic synthetic comparison plus approved, version-pinned source "
                "records; no field or scientific validation is claimed."
            ),
        },
        "supported_conditions": supported_conditions,
        "unsupported_conditions": unsupported_conditions,
        "tested_limits": {
            "resource_safety": {
                "maximum_plan_assignments": MAX_VALIDATION_ASSIGNMENTS,
                "maximum_calibration_observations": MAX_VALIDATION_OBSERVATIONS,
                "maximum_verification_upload_bytes": 10 * 1024 * 1024,
                "interpretation": (
                    "Provisional resource-safety guards; not validated operational capacity."
                ),
            },
            "comparison_ratio_tolerance": {"minimum": "0.750", "maximum": "1.250"},
            "coverage_model": coverage.model_snapshot.get("tested_limits", {}),
            "directional_model": directional.model_snapshot.get("tested_limits", {}),
            "calibration_parameters": calibration.parameters,
        },
        "sensitivity": {
            "coverage_distance_m": {
                "conservative": coverage.conservative_distance_m,
                "nominal": coverage.nominal_distance_m,
                "optimistic": coverage.optimistic_distance_m,
            },
            "directional_distance_m": {
                "talk_out": directional.talk_out_distance_m,
                "talk_in": directional.talk_in_distance_m,
                "probable_two_way": directional.probable_two_way_distance_m,
                "limiting_path": directional.limiting_path,
            },
            "incident_local_calibration_multiplier": calibration_multiplier,
        },
        "deterministic_observation_comparison": {
            "method": VALIDATION_METHOD_VERSION,
            "counts": comparison_counts,
            "observations": comparisons,
            "interpretation": (
                "Tolerance results are a repeatable software check against the selected "
                "synthetic fixture, not a claim of RF model accuracy."
            ),
        },
        "source_evidence": source_evidence,
        "disclaimer": VALIDATION_DISCLAIMER,
    }
    return result


def _mark_failed(bundle: Phase2ValidationBundle, *, code: str, message: str) -> None:
    bundle.job_state = Phase2ValidationBundle.JobState.FAILED
    bundle.progress_step = "failed"
    bundle.completed_at = timezone.now()
    bundle.failure_code = code[:80]
    bundle.failure_message = message[:240]
    bundle.save(
        update_fields=[
            "job_state",
            "progress_step",
            "completed_at",
            "failure_code",
            "failure_message",
            "updated_at",
        ]
    )


def run_validation_bundle(bundle: Phase2ValidationBundle) -> Phase2ValidationBundle:
    with transaction.atomic():
        bundle = Phase2ValidationBundle.objects.select_for_update().get(pk=bundle.pk)
        if bundle.job_state != Phase2ValidationBundle.JobState.QUEUED:
            raise ValidationError("Only queued Phase 2 validation work can be run.")
        bundle.job_state = Phase2ValidationBundle.JobState.RUNNING
        bundle.progress_step = "validating_sources"
        bundle.progress_percent = 10
        bundle.started_at = timezone.now()
        bundle.save(
            update_fields=[
                "job_state",
                "progress_step",
                "progress_percent",
                "started_at",
                "updated_at",
            ]
        )

    try:
        _validate_source_chain(
            incident=bundle.incident,
            approved_revision=bundle.approved_revision,
            haat_calculation=bundle.haat_calculation,
            coverage_estimate=bundle.coverage_estimate,
            directional_analysis=bundle.directional_analysis,
            calibration_set=bundle.calibration_set,
        )
        current_input = _input_snapshot(
            incident=bundle.incident,
            approved_revision=bundle.approved_revision,
            haat_calculation=bundle.haat_calculation,
            coverage_estimate=bundle.coverage_estimate,
            directional_analysis=bundle.directional_analysis,
            calibration_set=bundle.calibration_set,
        )
        if canonical_digest(current_input) != bundle.input_sha256:
            _mark_failed(
                bundle,
                code="source_changed",
                message=(
                    "A selected source changed after queueing. Create a new validation bundle "
                    "from current approved sources."
                ),
            )
            return Phase2ValidationBundle.objects.get(pk=bundle.pk)
        if bundle.haat_calculation.elevation_snapshot.current_state == "stale":
            _mark_failed(
                bundle,
                code="stale_elevation",
                message=(
                    "The selected elevation snapshot became stale. Recalculate against a current "
                    "approved elevation source."
                ),
            )
            return Phase2ValidationBundle.objects.get(pk=bundle.pk)
        result = _result_snapshot(bundle)
        with transaction.atomic():
            bundle = Phase2ValidationBundle.objects.select_for_update().get(pk=bundle.pk)
            bundle.result_snapshot = result
            bundle.result_sha256 = canonical_digest(result)
            bundle.job_state = Phase2ValidationBundle.JobState.COMPLETE
            bundle.progress_step = "complete"
            bundle.progress_percent = 100
            bundle.completed_at = timezone.now()
            bundle.save(
                update_fields=[
                    "result_snapshot",
                    "result_sha256",
                    "job_state",
                    "progress_step",
                    "progress_percent",
                    "completed_at",
                    "updated_at",
                ]
            )
        return bundle
    except ValidationError:
        logger.warning(
            "Phase 2 validation source check failed for bundle %s.",
            bundle.pk,
        )
        _mark_failed(
            bundle,
            code="source_validation_failed",
            message="Selected sources no longer satisfy Phase 2 validation requirements.",
        )
        return Phase2ValidationBundle.objects.get(pk=bundle.pk)
    except Exception:
        logger.exception(
            "Phase 2 validation internal failure for bundle %s.",
            bundle.pk,
        )
        _mark_failed(
            bundle,
            code="validation_internal_error",
            message=(
                "The validation run failed without changing source evidence. Review server logs "
                "and retry from a new queued record."
            ),
        )
        return Phase2ValidationBundle.objects.get(pk=bundle.pk)


@transaction.atomic
def cancel_validation_bundle(bundle: Phase2ValidationBundle) -> Phase2ValidationBundle:
    bundle = Phase2ValidationBundle.objects.select_for_update().get(pk=bundle.pk)
    if bundle.job_state != Phase2ValidationBundle.JobState.QUEUED:
        raise ValidationError("Only queued Phase 2 validation work can be cancelled.")
    bundle.job_state = Phase2ValidationBundle.JobState.CANCELLED
    bundle.progress_step = "cancelled"
    bundle.completed_at = timezone.now()
    bundle.failure_code = "cancelled_by_user"
    bundle.failure_message = "The queued validation run was cancelled before execution."
    bundle.save(
        update_fields=[
            "job_state",
            "progress_step",
            "completed_at",
            "failure_code",
            "failure_message",
            "updated_at",
        ]
    )
    return bundle


@transaction.atomic
def approve_validation_bundle(bundle: Phase2ValidationBundle, *, actor) -> Phase2ValidationBundle:
    bundle = Phase2ValidationBundle.objects.select_for_update().get(pk=bundle.pk)
    if bundle.status == Phase2ValidationBundle.Status.APPROVED:
        raise ValidationError("The Phase 2 validation bundle is already approved.")
    if bundle.job_state != Phase2ValidationBundle.JobState.COMPLETE:
        raise ValidationError("Only a completed Phase 2 validation bundle can be approved.")
    if stale_reasons(bundle):
        raise ValidationError(
            "The Phase 2 validation evidence is stale. Queue a new bundle from current sources."
        )
    if bundle.validation_profile_version not in getattr(
        settings, "ICT_APPROVED_PHASE2_VALIDATION_PROFILES", []
    ):
        raise ValidationError(
            "This exact Phase 2 validation profile has not passed the configured qualified "
            "RF/GIS, security/privacy, and maintainer gates."
        )
    bundle.status = Phase2ValidationBundle.Status.APPROVED
    bundle.approved_by = actor
    bundle.approved_at = timezone.now()
    bundle.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    return bundle


def validation_export_bytes(bundle: Phase2ValidationBundle) -> bytes:
    if bundle.status != Phase2ValidationBundle.Status.APPROVED:
        raise ValidationError("Only approved Phase 2 validation evidence can be exported.")
    reasons = stale_reasons(bundle)
    if reasons:
        raise ValidationError(
            {
                "detail": (
                    "The approved evidence is now stale and cannot be exported. Retain it for "
                    "history and approve a new bundle."
                ),
                "stale_reasons": reasons,
            }
        )
    document = {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "classification": NON_PRODUCTION_LABEL,
        "bundle": {
            "id": str(bundle.id),
            "incident_id": str(bundle.incident_id),
            "status": bundle.status,
            "approved_by_id": str(bundle.approved_by_id),
            "approved_at": bundle.approved_at.isoformat() if bundle.approved_at else None,
            "created_by_id": str(bundle.created_by_id),
            "created_at": bundle.created_at.isoformat(),
            "completed_at": bundle.completed_at.isoformat() if bundle.completed_at else None,
            "application_version": bundle.app_version,
            "validation_profile_id": bundle.validation_profile_id,
            "validation_profile_version": bundle.validation_profile_version,
            "input_sha256": bundle.input_sha256,
            "result_sha256": bundle.result_sha256,
        },
        "result": bundle.result_snapshot,
    }
    return (
        json.dumps(document, sort_keys=True, indent=2, default=str, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
