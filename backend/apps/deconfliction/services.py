from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.plans.models import PlanRevision
from apps.resources.models import ConventionalChannel

from .models import DeconflictionAnalysis
from .rules import (
    ADJACENT_THRESHOLD_HZ,
    DISCLAIMER,
    RULE_DEFINITIONS,
    RULE_SET_ID,
    RULE_SET_VERSION,
    evaluate,
    rule_set_status,
)


def canonical_digest(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def deconfliction_status() -> dict[str, Any]:
    approved = RULE_SET_VERSION in settings.ICT_APPROVED_DECONFLICTION_RULESETS
    return rule_set_status(approved=approved)


def _area_snapshot(assignment) -> list[dict[str, Any]]:
    areas: list[dict[str, Any]] = []
    for link in assignment.site_links.all():
        snapshot = deepcopy(link.site_snapshot)
        if not snapshot:
            raise ValidationError(
                f"Approved assignment {assignment.id} is missing its site snapshot."
            )
        try:
            latitude = Decimal(str(snapshot["latitude"]))
            longitude = Decimal(str(snapshot["longitude"]))
        except (InvalidOperation, KeyError, TypeError, ValueError) as exc:
            raise ValidationError(
                f"Approved assignment {assignment.id} has an invalid site snapshot."
            ) from exc
        if (
            not latitude.is_finite()
            or not Decimal("-90") <= latitude <= Decimal("90")
            or not longitude.is_finite()
            or not Decimal("-180") <= longitude <= Decimal("180")
        ):
            raise ValidationError(
                f"Approved assignment {assignment.id} has an invalid site coordinate."
            )
        for ring in snapshot.get("rings", []):
            if ring.get("type") not in {"operational", "coordination"}:
                continue
            radius_m = ring.get("radius_m")
            if not isinstance(radius_m, int) or radius_m < 1 or radius_m > 2_147_483_647:
                raise ValidationError(
                    f"Approved assignment {assignment.id} has an invalid area radius."
                )
            areas.append(
                {
                    "site_id": str(snapshot["site_id"]),
                    "site_name": str(snapshot["name"]),
                    "latitude": format(latitude, "f"),
                    "longitude": format(longitude, "f"),
                    "ring_type": ring["type"],
                    "radius_m": radius_m,
                    "label": str(ring.get("label", "")),
                }
            )
    return sorted(
        areas,
        key=lambda area: (
            area["site_name"],
            area["ring_type"],
            area["radius_m"],
            area["site_id"],
        ),
    )


def _assignment_snapshot(revision: PlanRevision) -> list[dict[str, Any]]:
    assignments = revision.assignments.select_related(
        "conventional_channel__release__source"
    ).prefetch_related("site_links")
    snapshots = []
    for assignment in assignments.order_by("position", "id"):
        resource_id = (
            str(assignment.conventional_channel_id)
            if assignment.conventional_channel_id
            else assignment.resource_snapshot.get("resource_id")
        )
        snapshots.append(
            {
                "id": str(assignment.id),
                "position": assignment.position,
                "function": assignment.function,
                "channel_name": assignment.channel_name,
                "assignment": assignment.assignment,
                "resource_id": resource_id,
                "resource_snapshot": deepcopy(assignment.resource_snapshot),
                "rx_frequency_hz": assignment.rx_frequency_hz,
                "tx_frequency_hz": assignment.tx_frequency_hz,
                "rx_squelch": assignment.rx_squelch,
                "tx_squelch": assignment.tx_squelch,
                "mode": assignment.mode,
                "areas": _area_snapshot(assignment),
            }
        )
    return snapshots


def _resource_snapshot(resources: list[ConventionalChannel]) -> list[dict[str, Any]]:
    snapshots = []
    for resource in resources:
        if not resource.is_active:
            raise ValidationError({"active_resources": f"Resource {resource.id} is not active."})
        if resource.release.effective_status != resource.release.Status.EFFECTIVE:
            raise ValidationError(
                {
                    "active_resources": (
                        f"Resource {resource.id} does not belong to an effective release."
                    )
                }
            )
        snapshots.append(
            {
                "id": str(resource.id),
                "identifier": resource.identifier,
                "name": resource.name,
                "rx_frequency_hz": resource.rx_frequency_hz,
                "tx_frequency_hz": resource.tx_frequency_hz,
                "rx_squelch": resource.rx_squelch,
                "tx_squelch": resource.tx_squelch,
                "mode": resource.mode,
                "release": resource.release.version,
                "source": resource.release.source.slug,
                "source_type": resource.release.source.source_type,
                "content_sha256": resource.release.content_sha256,
            }
        )
    return sorted(snapshots, key=lambda resource: resource["id"])


@transaction.atomic
def create_deconfliction_analysis(
    *,
    incident,
    approved_revision: PlanRevision,
    active_resources: list[ConventionalChannel],
    actor,
) -> DeconflictionAnalysis:
    if incident.archived_at is not None:
        raise ValidationError({"incident": "Archived incidents cannot be analyzed."})
    revision = (
        PlanRevision.objects.select_for_update()
        .select_related("plan__incident", "approved_by")
        .get(pk=approved_revision.pk)
    )
    if revision.plan.incident_id != incident.id:
        raise ValidationError(
            {"approved_revision": "The approved revision belongs to another incident."}
        )
    if revision.status != PlanRevision.Status.APPROVED:
        raise ValidationError(
            {"approved_revision": "Deconfliction requires an approved ICS-205 revision."}
        )
    if not revision.assignments.exists():
        raise ValidationError(
            {"approved_revision": "The approved revision contains no assignments."}
        )
    if len(active_resources) > 500:
        raise ValidationError({"active_resources": "Select no more than 500 active resources."})
    if len({resource.id for resource in active_resources}) != len(active_resources):
        raise ValidationError({"active_resources": "Each active resource may be selected once."})
    locked_resources = list(
        ConventionalChannel.objects.select_related("release__source")
        .select_for_update()
        .filter(pk__in=[resource.pk for resource in active_resources])
    )
    if len(locked_resources) != len(active_resources):
        raise ValidationError(
            {"active_resources": "One or more selected resources no longer exist."}
        )

    assignment_snapshot = _assignment_snapshot(revision)
    resource_snapshot = _resource_snapshot(locked_resources)
    input_snapshot = {
        "schema_version": "rf-deconfliction-input-v1",
        "incident_id": str(incident.id),
        "approved_revision": {
            "id": str(revision.id),
            "plan_id": str(revision.plan_id),
            "number": revision.number,
            "approved_at": revision.approved_at.isoformat(),
            "approved_by_id": str(revision.approved_by_id),
        },
        "rule_set_id": RULE_SET_ID,
        "rule_set_version": RULE_SET_VERSION,
        "adjacent_channel_threshold_hz": ADJACENT_THRESHOLD_HZ,
        "assignments": assignment_snapshot,
        "selected_active_resources": resource_snapshot,
    }
    input_sha256 = canonical_digest(input_snapshot)
    warnings = evaluate(assignment_snapshot, resource_snapshot)
    result_snapshot = {
        "schema_version": "rf-deconfliction-result-v1",
        "rule_set_id": RULE_SET_ID,
        "rule_set_version": RULE_SET_VERSION,
        "input_sha256": input_sha256,
        "rule_definitions": RULE_DEFINITIONS,
        "warning_count": len(warnings),
        "warnings": warnings,
        "disclaimer": DISCLAIMER,
    }
    return DeconflictionAnalysis.objects.create(
        incident=incident,
        approved_revision=revision,
        rule_set_id=RULE_SET_ID,
        rule_set_version=RULE_SET_VERSION,
        input_snapshot=input_snapshot,
        input_sha256=input_sha256,
        result_snapshot=result_snapshot,
        result_sha256=canonical_digest(result_snapshot),
        warning_count=len(warnings),
        created_by=actor,
    )


@transaction.atomic
def approve_deconfliction_analysis(
    analysis: DeconflictionAnalysis,
    *,
    actor,
) -> DeconflictionAnalysis:
    analysis = DeconflictionAnalysis.objects.select_for_update().get(pk=analysis.pk)
    if analysis.status == DeconflictionAnalysis.Status.APPROVED:
        raise ValidationError("The deconfliction analysis is already approved.")
    if analysis.rule_set_version not in settings.ICT_APPROVED_DECONFLICTION_RULESETS:
        raise ValidationError(
            "The exact deconfliction rule set has not passed the practitioner gate."
        )
    if canonical_digest(analysis.input_snapshot) != analysis.input_sha256:
        raise ValidationError("The retained deconfliction input digest is invalid.")
    if canonical_digest(analysis.result_snapshot) != analysis.result_sha256:
        raise ValidationError("The retained deconfliction result digest is invalid.")
    DeconflictionAnalysis.objects.filter(pk=analysis.pk).update(
        status=DeconflictionAnalysis.Status.APPROVED,
        approved_by=actor,
        approved_at=timezone.now(),
    )
    return DeconflictionAnalysis.objects.get(pk=analysis.pk)
