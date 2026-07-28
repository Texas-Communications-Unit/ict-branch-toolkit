from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.forms.models import model_to_dict
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.policy import PLAN_EDIT, PLAN_VIEW, user_has_permission
from apps.audit.services import record_event
from apps.incidents.models import Incident
from apps.plans.models import Assignment, PlanRevision
from apps.plans.serializers import AssignmentSerializer, PlanRevisionSerializer
from apps.resources.models import ResourceRelease
from apps.rf_analysis.models import TerrainAnalysis
from apps.rf_analysis.serializers import TerrainAnalysisSerializer
from apps.sites.models import RadioSite

from .models import OfflineConflictResolution, OfflineMutationReceipt, OfflinePackage

OFFLINE_SCHEMA_VERSION = "offline-package-v1"
MUTATION_SCHEMA_VERSION = "offline-mutation-v1"
SUPPORTED_OPERATIONS = (
    "revision.update",
    "assignment.create",
    "assignment.update",
    "assignment.delete",
)
UNSUPPORTED_OPERATIONS = (
    "approve or publish a plan revision",
    "create an official export",
    "change incident membership or access",
    "import or refresh a reference library",
    "run terrain, RF, geocoder, RadioReference, or other network-backed providers",
    "upload or package attachments",
)
ASSIGNMENT_FIELDS = {
    "position",
    "function",
    "channel_name",
    "assignment",
    "conventional_channel",
    "trunked_talkgroup",
    "rx_frequency_hz",
    "rx_squelch",
    "tx_frequency_hz",
    "tx_squelch",
    "mode",
    "remarks",
    "structured_note",
    "contact_name",
    "site_address",
    "phone_numbers",
    "contact_24_hour",
}
REVISION_FIELDS = {
    "prepared_by_name",
    "prepared_by_position",
    "prepared_at",
}


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        cls=DjangoJSONEncoder,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder))


def _iso(value) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


def offline_status() -> dict[str, Any]:
    return {
        "schema_version": OFFLINE_SCHEMA_VERSION,
        "enabled": settings.ICT_OFFLINE_ENABLED,
        "approved_for_non_synthetic_use": (settings.ICT_OFFLINE_APPROVED_FOR_NON_SYNTHETIC_USE),
        "protection": {
            "browser_storage": "AES-256-GCM encrypted IndexedDB envelope",
            "key_derivation": "PBKDF2-SHA-256 with per-package salt and 310000 iterations",
            "key_persistence": "The unlock key remains in memory only.",
            "limitation": (
                "Browser encryption protects data at rest after lock. It does not protect an "
                "unlocked session or a compromised browser/device."
            ),
        },
        "supported_operations": list(SUPPORTED_OPERATIONS),
        "unsupported_operations": list(UNSUPPORTED_OPERATIONS),
        "limits": {
            "maximum_package_bytes": settings.ICT_OFFLINE_MAX_PACKAGE_BYTES,
            "maximum_queue_items": settings.ICT_OFFLINE_MAX_QUEUE_ITEMS,
            "default_expiration_hours": settings.ICT_OFFLINE_DEFAULT_TTL_HOURS,
            "maximum_expiration_hours": settings.ICT_OFFLINE_MAX_TTL_HOURS,
            "clock_skew_tolerance_seconds": settings.ICT_OFFLINE_CLOCK_SKEW_SECONDS,
        },
        "conflict_policy": (
            "No last-writer-wins behavior. Stale, locked, revoked, reordered, altered, and "
            "unsupported changes require an explicit discard or refresh-and-requeue decision."
        ),
        "classification": "Inherits the highest classification of selected incident content.",
        "warning": (
            "Offline operation is provisional and synthetic-only until security, privacy, "
            "records-management, operational, and maintainer approval is recorded."
        ),
    }


def revision_digest(revision: PlanRevision) -> str:
    revision = (
        PlanRevision.objects.select_related("plan__incident")
        .prefetch_related("assignments", "relationships__assignments")
        .get(pk=revision.pk)
    )
    return digest(PlanRevisionSerializer(revision).data)


def _serialize_release(release: ResourceRelease) -> dict[str, Any]:
    return {
        "id": str(release.id),
        "source": {
            "id": str(release.source_id),
            "slug": release.source.slug,
            "name": release.source.name,
            "source_type": release.source.source_type,
            "authoritative_url": release.source.authoritative_url,
        },
        "version": release.version,
        "released_on": _iso(release.released_on),
        "effective_status": release.effective_status,
        "content_sha256": release.content_sha256,
        "document_title": release.document_title,
        "publisher": release.publisher,
        "retrieved_on": _iso(release.retrieved_on),
        "permitted_use": release.permitted_use,
        "transformation_method": release.transformation_method,
        "conventional_channels": [
            _json_safe(model_to_dict(channel))
            for channel in release.conventional_channels.order_by("name", "identifier")
        ],
        "trunked_talkgroups": [
            _json_safe(model_to_dict(talkgroup))
            for talkgroup in release.trunked_talkgroups.order_by(
                "system_name", "name", "identifier"
            )
        ],
    }


def _serialize_site(site: RadioSite) -> dict[str, Any]:
    site_data = _json_safe(model_to_dict(site, exclude=["location"]))
    site_data["id"] = str(site.id)
    site_data["rings"] = [
        _json_safe(model_to_dict(ring)) for ring in site.rings.order_by("ring_type", "radius_m")
    ]
    return site_data


def _build_payload(
    *,
    incident: Incident,
    revisions: list[PlanRevision],
    releases: list[ResourceRelease],
    sites: list[RadioSite],
    terrain_analyses: list[TerrainAnalysis],
    include_map: bool,
) -> dict[str, Any]:
    return {
        "schema_version": OFFLINE_SCHEMA_VERSION,
        "generated_at": _iso(timezone.now()),
        "incident": {
            "id": str(incident.id),
            "name": incident.name,
            "incident_number": incident.incident_number,
            "status": incident.status,
            "updated_at": _iso(incident.updated_at),
        },
        "revisions": [_json_safe(PlanRevisionSerializer(revision).data) for revision in revisions],
        "resource_releases": [_serialize_release(release) for release in releases],
        "sites": [_serialize_site(site) for site in sites],
        "terrain_analyses": [
            _json_safe(TerrainAnalysisSerializer(analysis).data) for analysis in terrain_analyses
        ],
        "offline_map": (
            {
                "format": "GeoJSON-compatible site snapshot",
                "site_ids": [str(site.id) for site in sites],
                "network_tiles_included": False,
                "warning": (
                    "No third-party basemap tiles are packaged. Selected site coordinates and "
                    "manual rings remain available for the offline vector view."
                ),
            }
            if include_map
            else None
        ),
        "attachments": [],
        "capabilities": {
            "supported_operations": list(SUPPORTED_OPERATIONS),
            "unsupported_operations": list(UNSUPPORTED_OPERATIONS),
            "approved_revisions_read_only": True,
        },
    }


def create_package(
    *,
    actor,
    incident_id,
    device_id,
    expires_in_hours: int,
    selection: dict[str, Any],
) -> OfflinePackage:
    if not settings.ICT_OFFLINE_ENABLED:
        raise ValidationError(
            "Offline packaging is disabled until the documented human gate is approved."
        )
    try:
        incident = Incident.objects.get(pk=incident_id, archived_at__isnull=True)
    except Incident.DoesNotExist as exc:
        raise ValidationError({"incident": "Select an active incident."}) from exc
    if not user_has_permission(actor, PLAN_VIEW, incident):
        raise PermissionDenied("Your incident role cannot package this incident.")

    revisions = list(
        PlanRevision.objects.filter(
            pk__in=selection["revision_ids"],
            plan__incident=incident,
        )
        .select_related("plan__incident")
        .prefetch_related("assignments", "relationships__assignments")
    )
    if len(revisions) != len(selection["revision_ids"]):
        raise ValidationError(
            {"selection": {"revision_ids": "Every revision must belong to the incident."}}
        )
    by_revision_id = {revision.id: revision for revision in revisions}
    revisions = [by_revision_id[item_id] for item_id in selection["revision_ids"]]

    releases = list(
        ResourceRelease.objects.filter(pk__in=selection["resource_release_ids"])
        .select_related("source")
        .prefetch_related("conventional_channels", "trunked_talkgroups")
    )
    if len(releases) != len(selection["resource_release_ids"]):
        raise ValidationError(
            {"selection": {"resource_release_ids": "A selected release was not found."}}
        )
    by_release_id = {release.id: release for release in releases}
    releases = [by_release_id[item_id] for item_id in selection["resource_release_ids"]]

    sites = list(
        RadioSite.objects.filter(
            pk__in=selection["site_ids"],
            incident=incident,
            archived_at__isnull=True,
        ).prefetch_related("rings")
    )
    if len(sites) != len(selection["site_ids"]):
        raise ValidationError(
            {"selection": {"site_ids": "Every selected site must belong to the incident."}}
        )
    by_site_id = {site.id: site for site in sites}
    sites = [by_site_id[item_id] for item_id in selection["site_ids"]]

    terrain_analyses = list(
        TerrainAnalysis.objects.filter(
            pk__in=selection["terrain_analysis_ids"],
            incident=incident,
        ).select_related("incident", "site", "coverage_estimate")
    )
    if len(terrain_analyses) != len(selection["terrain_analysis_ids"]):
        raise ValidationError(
            {
                "selection": {
                    "terrain_analysis_ids": (
                        "Every selected terrain analysis must belong to the incident."
                    )
                }
            }
        )
    by_terrain_id = {analysis.id: analysis for analysis in terrain_analyses}
    terrain_analyses = [by_terrain_id[item_id] for item_id in selection["terrain_analysis_ids"]]

    payload = _build_payload(
        incident=incident,
        revisions=revisions,
        releases=releases,
        sites=sites,
        terrain_analyses=terrain_analyses,
        include_map=selection["include_map"],
    )
    payload_sha256 = digest(payload)
    payload_size = len(canonical_json(payload).encode("utf-8"))
    if payload_size > settings.ICT_OFFLINE_MAX_PACKAGE_BYTES:
        raise ValidationError(
            {
                "selection": (
                    f"The selected package is {payload_size} bytes; the configured maximum is "
                    f"{settings.ICT_OFFLINE_MAX_PACKAGE_BYTES} bytes."
                )
            }
        )
    scope = {
        key: [str(value) for value in selection[key]]
        for key in (
            "revision_ids",
            "resource_release_ids",
            "site_ids",
            "terrain_analysis_ids",
            "attachment_ids",
        )
    }
    scope["include_map"] = selection["include_map"]
    revision_state = {
        str(revision.id): {
            "server_sha256": revision_digest(revision),
            "status": revision.status,
        }
        for revision in revisions
    }
    manifest = {
        "schema_version": OFFLINE_SCHEMA_VERSION,
        "incident_id": str(incident.id),
        "actor_id": actor.pk,
        "device_id": str(device_id),
        "scope": scope,
        "payload_sha256": payload_sha256,
        "payload_bytes": payload_size,
        "revision_state": revision_state,
        "classification": (
            "Synthetic-only unless an approved deployment-specific classification applies."
        ),
    }
    manifest_sha256 = digest(manifest)
    package = OfflinePackage.objects.create(
        incident=incident,
        requested_by=actor,
        device_id=device_id,
        scope=scope,
        payload_snapshot=payload,
        manifest=manifest,
        manifest_sha256=manifest_sha256,
        revision_state=revision_state,
        last_chain_sha256=manifest_sha256,
        expires_at=timezone.now() + timedelta(hours=expires_in_hours),
    )
    record_event(
        actor=actor,
        action="offline_package.created",
        target=package,
        details={
            "incident_id": str(incident.id),
            "device_id": str(device_id),
            "manifest_sha256": manifest_sha256,
            "payload_bytes": payload_size,
            "revision_count": len(revisions),
            "resource_release_count": len(releases),
            "site_count": len(sites),
            "terrain_analysis_count": len(terrain_analyses),
            "expires_at": _iso(package.expires_at),
        },
    )
    return package


def package_current_status(package: OfflinePackage, actor=None) -> str:
    if package.status in {
        OfflinePackage.Status.PURGED,
        OfflinePackage.Status.REVOKED,
    }:
        return package.status
    if package.expires_at <= timezone.now():
        if package.status != OfflinePackage.Status.EXPIRED:
            OfflinePackage.objects.filter(pk=package.pk).update(
                status=OfflinePackage.Status.EXPIRED
            )
            package.status = OfflinePackage.Status.EXPIRED
            record_event(
                actor=actor,
                action="offline_package.expired",
                target=package,
                details={"manifest_sha256": package.manifest_sha256},
            )
        return OfflinePackage.Status.EXPIRED
    if actor and not user_has_permission(actor, PLAN_VIEW, package.incident):
        OfflinePackage.objects.filter(pk=package.pk).update(
            status=OfflinePackage.Status.REVOKED,
            revoked_at=timezone.now(),
        )
        package.status = OfflinePackage.Status.REVOKED
        record_event(
            actor=actor,
            action="offline_package.revoked",
            target=package,
            details={"reason": "incident_access_removed"},
        )
        return OfflinePackage.Status.REVOKED
    return package.status


def _mutation_document(package: OfflinePackage, mutation: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": MUTATION_SCHEMA_VERSION,
        "package_id": str(package.id),
        "mutation_id": str(mutation["id"]),
        "sequence": mutation["sequence"],
        "actor_id": mutation["actor_id"],
        "device_id": str(mutation["device_id"]),
        "operation": mutation["operation"],
        "object_id": str(mutation["object_id"]) if mutation.get("object_id") else None,
        "revision_id": str(mutation["revision_id"]),
        "previous_hash": mutation["previous_hash"],
        "payload_sha256": mutation["payload_sha256"],
        "base_updated_at": _iso(mutation.get("base_updated_at")),
        "occurred_at_client": _iso(mutation["occurred_at_client"]),
    }


def _receipt(
    *,
    package: OfflinePackage,
    mutation: dict[str, Any],
    status: str,
    result: dict[str, Any],
) -> OfflineMutationReceipt:
    receipt = OfflineMutationReceipt.objects.create(
        id=mutation["id"],
        package=package,
        sequence=mutation["sequence"],
        actor_id_snapshot=mutation["actor_id"],
        device_id=mutation["device_id"],
        operation=mutation["operation"],
        object_id=mutation.get("object_id"),
        revision_id=mutation["revision_id"],
        previous_hash=mutation["previous_hash"],
        payload_sha256=mutation["payload_sha256"],
        mutation_sha256=mutation["mutation_sha256"],
        payload_snapshot=mutation["payload"],
        base_updated_at=mutation.get("base_updated_at"),
        occurred_at_client=mutation["occurred_at_client"],
        status=status,
        result=result,
    )
    package.last_sequence = mutation["sequence"]
    package.last_chain_sha256 = mutation["mutation_sha256"]
    package.save(update_fields=["last_sequence", "last_chain_sha256", "updated_at"])
    return receipt


def _resource_is_in_scope(package: OfflinePackage, resource) -> bool:
    if resource is None:
        return True
    return str(resource.release_id) in package.scope["resource_release_ids"]


def _apply_mutation(
    package: OfflinePackage,
    mutation: dict[str, Any],
    actor,
) -> tuple[str, dict[str, Any]]:
    try:
        revision = (
            PlanRevision.objects.select_for_update()
            .select_related("plan__incident")
            .prefetch_related("assignments", "relationships__assignments")
            .get(pk=mutation["revision_id"], plan__incident=package.incident)
        )
    except PlanRevision.DoesNotExist:
        return OfflineMutationReceipt.Status.CONFLICT, {
            "code": "revision_missing",
            "detail": "The selected revision is no longer available.",
            "resolution_required": True,
        }
    if str(revision.id) not in package.scope["revision_ids"]:
        return OfflineMutationReceipt.Status.REJECTED, {
            "code": "outside_package_scope",
            "detail": "The mutation references a revision that was not packaged.",
        }
    if revision.status != PlanRevision.Status.DRAFT:
        return OfflineMutationReceipt.Status.CONFLICT, {
            "code": "revision_locked",
            "detail": "Approved revisions remain read-only and cannot accept offline changes.",
            "resolution_required": True,
        }
    expected_state = package.revision_state.get(str(revision.id), {})
    current_digest = revision_digest(revision)
    if current_digest != expected_state.get("server_sha256"):
        return OfflineMutationReceipt.Status.CONFLICT, {
            "code": "stale_base_revision",
            "detail": (
                "The server revision changed after packaging. Review current and local values; "
                "no change was applied."
            ),
            "expected_sha256": expected_state.get("server_sha256"),
            "current_sha256": current_digest,
            "resolution_required": True,
        }

    operation = mutation["operation"]
    payload = mutation["payload"]
    object_id = mutation.get("object_id")
    try:
        if operation == "revision.update":
            unexpected = set(payload) - REVISION_FIELDS
            if unexpected:
                raise ValidationError(
                    {"payload": f"Unsupported revision fields: {', '.join(sorted(unexpected))}"}
                )
            if object_id and object_id != revision.id:
                raise ValidationError({"object_id": "The object must be the selected revision."})
            serializer = PlanRevisionSerializer(revision, data=payload, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            target = revision
        elif operation == "assignment.create":
            unexpected = set(payload) - ASSIGNMENT_FIELDS
            if unexpected:
                raise ValidationError(
                    {"payload": f"Unsupported assignment fields: {', '.join(sorted(unexpected))}"}
                )
            if not object_id:
                raise ValidationError({"object_id": "A stable client object ID is required."})
            if Assignment.objects.filter(pk=object_id).exists():
                raise ValidationError({"object_id": "The assignment ID already exists."})
            serializer = AssignmentSerializer(data={**payload, "revision": str(revision.id)})
            serializer.is_valid(raise_exception=True)
            if not _resource_is_in_scope(
                package, serializer.validated_data.get("conventional_channel")
            ) or not _resource_is_in_scope(
                package, serializer.validated_data.get("trunked_talkgroup")
            ):
                raise ValidationError(
                    {"payload": "Referenced channel resources must be included in the package."}
                )
            target = serializer.save(id=object_id)
        else:
            if not object_id:
                raise ValidationError({"object_id": "Select an assignment."})
            try:
                assignment = Assignment.objects.select_for_update().get(
                    pk=object_id,
                    revision=revision,
                )
            except Assignment.DoesNotExist:
                return OfflineMutationReceipt.Status.CONFLICT, {
                    "code": "assignment_missing",
                    "detail": "The assignment no longer exists on the server.",
                    "resolution_required": True,
                }
            if (
                not mutation.get("base_updated_at")
                or assignment.updated_at != mutation["base_updated_at"]
            ):
                return OfflineMutationReceipt.Status.CONFLICT, {
                    "code": "stale_object",
                    "detail": (
                        "The assignment changed after it was packaged. Review both versions; "
                        "no change was applied."
                    ),
                    "resolution_required": True,
                }
            if operation == "assignment.update":
                unexpected = set(payload) - ASSIGNMENT_FIELDS
                if unexpected:
                    raise ValidationError(
                        {
                            "payload": (
                                f"Unsupported assignment fields: {', '.join(sorted(unexpected))}"
                            )
                        }
                    )
                serializer = AssignmentSerializer(assignment, data=payload, partial=True)
                serializer.is_valid(raise_exception=True)
                if not _resource_is_in_scope(
                    package, serializer.validated_data.get("conventional_channel")
                ) or not _resource_is_in_scope(
                    package, serializer.validated_data.get("trunked_talkgroup")
                ):
                    raise ValidationError(
                        {
                            "payload": (
                                "Referenced channel resources must be included in the package."
                            )
                        }
                    )
                target = serializer.save()
            elif operation == "assignment.delete":
                if payload:
                    raise ValidationError({"payload": "Delete does not accept content."})
                target = revision
                assignment.delete()
            else:
                return OfflineMutationReceipt.Status.REJECTED, {
                    "code": "unsupported_operation",
                    "detail": "This action is not offline-capable.",
                }
    except ValidationError as exc:
        return OfflineMutationReceipt.Status.REJECTED, {
            "code": "invalid_payload",
            "detail": exc.detail,
        }

    new_digest = revision_digest(revision)
    package.revision_state[str(revision.id)] = {
        "server_sha256": new_digest,
        "status": PlanRevision.Status.DRAFT,
    }
    package.save(update_fields=["revision_state", "updated_at"])
    record_event(
        actor=actor,
        action=f"offline_{operation.replace('.', '_')}.applied",
        target=target,
        details={
            "package_id": str(package.id),
            "mutation_id": str(mutation["id"]),
            "sequence": mutation["sequence"],
            "mutation_sha256": mutation["mutation_sha256"],
            "revision_id": str(revision.id),
            "revision_sha256": new_digest,
        },
    )
    return OfflineMutationReceipt.Status.APPLIED, {
        "code": "applied",
        "detail": "The ordered offline change was applied.",
        "revision_sha256": new_digest,
    }


@transaction.atomic
def synchronize_package(
    *,
    package: OfflinePackage,
    actor,
    client_now,
    mutations: list[dict[str, Any]],
) -> dict[str, Any]:
    package = (
        OfflinePackage.objects.select_for_update()
        .select_related("incident", "requested_by")
        .get(pk=package.pk)
    )
    current_status = package_current_status(package, actor)
    if current_status != OfflinePackage.Status.ACTIVE:
        raise PermissionDenied(
            f"This package is {current_status}; no offline changes were accepted."
        )
    if package.requested_by_id != actor.pk:
        raise PermissionDenied("Only the user who created this package may synchronize it.")
    if not user_has_permission(actor, PLAN_EDIT, package.incident):
        package.status = OfflinePackage.Status.REVOKED
        package.revoked_at = timezone.now()
        package.save(update_fields=["status", "revoked_at", "updated_at"])
        record_event(
            actor=actor,
            action="offline_package.revoked",
            target=package,
            details={"reason": "incident_access_or_edit_permission_removed"},
        )
        raise PermissionDenied("Incident access was revoked; the package must be locked or purged.")

    skew_seconds = abs((timezone.now() - client_now).total_seconds())
    if skew_seconds > settings.ICT_OFFLINE_CLOCK_SKEW_SECONDS:
        raise ValidationError(
            {
                "client_now": (
                    f"Client clock differs from the server by {round(skew_seconds)} seconds. "
                    "Correct the device clock before synchronization."
                )
            }
        )

    results = []
    unresolved = package.mutation_receipts.filter(
        status=OfflineMutationReceipt.Status.CONFLICT,
        resolution__isnull=True,
    ).exists()
    for mutation in mutations:
        existing = OfflineMutationReceipt.objects.filter(pk=mutation["id"]).first()
        if existing:
            if (
                existing.package_id == package.id
                and existing.mutation_sha256 == mutation["mutation_sha256"]
            ):
                results.append(
                    {
                        "id": str(existing.id),
                        "sequence": existing.sequence,
                        "status": "duplicate",
                        "result": existing.result,
                    }
                )
                continue
            raise ValidationError({"mutations": "A mutation ID was reused with different content."})
        if mutation["actor_id"] != actor.pk or mutation["device_id"] != package.device_id:
            raise ValidationError(
                {"mutations": "Actor and device context must match the package manifest."}
            )
        if mutation["sequence"] != package.last_sequence + 1:
            raise ValidationError(
                {
                    "mutations": (
                        f"Expected sequence {package.last_sequence + 1}; received "
                        f"{mutation['sequence']}."
                    )
                }
            )
        if mutation["previous_hash"] != package.last_chain_sha256:
            raise ValidationError(
                {"mutations": "The local mutation hash chain is broken or reordered."}
            )
        computed_payload_sha256 = digest(mutation["payload"])
        if computed_payload_sha256 != mutation["payload_sha256"]:
            raise ValidationError({"mutations": "The mutation payload digest does not match."})
        computed_mutation_sha256 = digest(_mutation_document(package, mutation))
        if computed_mutation_sha256 != mutation["mutation_sha256"]:
            raise ValidationError({"mutations": "The mutation digest does not match."})

        if unresolved:
            receipt_status = OfflineMutationReceipt.Status.CONFLICT
            result = {
                "code": "earlier_conflict_unresolved",
                "detail": (
                    "Resolve the earlier conflict before later ordered changes can be applied."
                ),
                "resolution_required": True,
            }
        else:
            receipt_status, result = _apply_mutation(package, mutation, actor)
        receipt = _receipt(
            package=package,
            mutation=mutation,
            status=receipt_status,
            result=result,
        )
        unresolved = unresolved or receipt_status == OfflineMutationReceipt.Status.CONFLICT
        results.append(
            {
                "id": str(receipt.id),
                "sequence": receipt.sequence,
                "status": receipt.status,
                "result": receipt.result,
            }
        )

    record_event(
        actor=actor,
        action="offline_package.synchronized",
        target=package,
        details={
            "accepted_count": sum(item["status"] == "applied" for item in results),
            "conflict_count": sum(item["status"] == "conflict" for item in results),
            "duplicate_count": sum(item["status"] == "duplicate" for item in results),
            "rejected_count": sum(item["status"] == "rejected" for item in results),
            "last_sequence": package.last_sequence,
            "last_chain_sha256": package.last_chain_sha256,
        },
    )
    return {
        "package_id": str(package.id),
        "status": package.status,
        "partial": any(item["status"] != "applied" for item in results),
        "results": results,
        "last_sequence": package.last_sequence,
        "last_chain_sha256": package.last_chain_sha256,
    }


@transaction.atomic
def resolve_conflict(
    *,
    package: OfflinePackage,
    actor,
    mutation_id,
    decision: str,
    explanation: str,
) -> OfflineConflictResolution:
    package = (
        OfflinePackage.objects.select_for_update().select_related("incident").get(pk=package.pk)
    )
    if package_current_status(package, actor) not in {
        OfflinePackage.Status.ACTIVE,
        OfflinePackage.Status.LOCKED,
    }:
        raise PermissionDenied("This package cannot accept conflict decisions.")
    if package.requested_by_id != actor.pk or not user_has_permission(
        actor, PLAN_EDIT, package.incident
    ):
        raise PermissionDenied("Your current incident role cannot resolve this conflict.")
    try:
        receipt = package.mutation_receipts.get(
            pk=mutation_id,
            status=OfflineMutationReceipt.Status.CONFLICT,
        )
    except OfflineMutationReceipt.DoesNotExist as exc:
        raise ValidationError({"mutation_id": "Select an unresolved conflict."}) from exc
    if hasattr(receipt, "resolution"):
        raise ValidationError({"mutation_id": "This conflict already has a decision."})
    resolution = OfflineConflictResolution.objects.create(
        receipt=receipt,
        decision=decision,
        explanation=explanation,
        resolved_by=actor,
    )
    record_event(
        actor=actor,
        action="offline_conflict.resolved",
        target=resolution,
        details={
            "package_id": str(package.id),
            "mutation_id": str(receipt.id),
            "decision": decision,
            "mutation_sha256": receipt.mutation_sha256,
        },
    )
    return resolution


def support_bundle(package: OfflinePackage) -> dict[str, Any]:
    receipts = package.mutation_receipts.order_by("sequence")
    return {
        "schema_version": "offline-support-bundle-v1",
        "generated_at": _iso(timezone.now()),
        "package": {
            "id": str(package.id),
            "status": package.status,
            "manifest_sha256": package.manifest_sha256,
            "device_id": str(package.device_id),
            "created_at": _iso(package.created_at),
            "expires_at": _iso(package.expires_at),
            "last_sequence": package.last_sequence,
            "last_chain_sha256": package.last_chain_sha256,
        },
        "receipt_summary": [
            {
                "id": str(receipt.id),
                "sequence": receipt.sequence,
                "operation": receipt.operation,
                "status": receipt.status,
                "mutation_sha256": receipt.mutation_sha256,
                "result_code": receipt.result.get("code"),
                "resolved": hasattr(receipt, "resolution"),
            }
            for receipt in receipts
        ],
        "excluded": [
            "authentication tokens",
            "encryption keys and passphrases",
            "encrypted package ciphertext",
            "incident payload content",
            "mutation payload content",
            "frequencies, coordinates, names, and notes",
        ],
    }
