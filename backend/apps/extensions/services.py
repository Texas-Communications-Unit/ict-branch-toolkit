from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.audit.services import record_event
from apps.plans.models import PlanRevision

from .models import ExtensionExecution, ExtensionInstallation
from .registry import (
    MANIFESTS,
    SUPPORTED_CONTRACT_VERSIONS,
    get_capability,
    get_manifest,
)


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def extension_catalog() -> list[dict[str, Any]]:
    installations = {
        item.extension_key: item
        for item in ExtensionInstallation.objects.all().order_by("extension_key")
    }
    catalog = []
    for extension_key in sorted(MANIFESTS):
        manifest = get_manifest(extension_key)
        installation = installations.get(extension_key)
        compatible = manifest["contract_version"] in SUPPORTED_CONTRACT_VERSIONS
        current = bool(
            installation
            and installation.extension_version == manifest["version"]
            and installation.contract_version == manifest["contract_version"]
            and installation.manifest_sha256 == canonical_digest(manifest)
        )
        enabled = bool(installation and installation.enabled and compatible and current)
        if not installation:
            message = "Not installed. An administrator must install and enable this extension."
        elif not current:
            message = (
                "Installed manifest does not match the server registry. "
                "Leave disabled and review the version before reinstalling."
            )
        elif not installation.enabled:
            message = "Installed but disabled. An administrator must enable this extension."
        elif not compatible:
            message = f"Contract {manifest['contract_version']} is incompatible with this server."
        else:
            message = "Installed, enabled, and contract-compatible."
        catalog.append(
            {
                "manifest": manifest,
                "installed": installation is not None,
                "enabled": enabled,
                "compatible": compatible and current,
                "installation_id": str(installation.id) if installation else None,
                "operator_message": message,
            }
        )
    return catalog


@transaction.atomic
def install_extension(*, extension_key: str, contract_version: str, actor):
    try:
        manifest = get_manifest(extension_key)
    except KeyError as exc:
        raise ValidationError(
            {"extension_key": "The requested extension is not in the server registry."}
        ) from exc
    if contract_version not in SUPPORTED_CONTRACT_VERSIONS:
        raise ValidationError(
            {
                "contract_version": (
                    f"Contract {contract_version} is not supported. "
                    f"Supported contracts: {', '.join(SUPPORTED_CONTRACT_VERSIONS)}."
                )
            }
        )
    if contract_version != manifest["contract_version"]:
        raise ValidationError(
            {
                "contract_version": (
                    f"Extension {extension_key} requires contract "
                    f"{manifest['contract_version']}; requested {contract_version}."
                )
            }
        )
    manifest_sha256 = canonical_digest(manifest)
    installation, created = ExtensionInstallation.objects.select_for_update().get_or_create(
        extension_key=extension_key,
        defaults={
            "extension_version": manifest["version"],
            "contract_version": manifest["contract_version"],
            "manifest_snapshot": manifest,
            "manifest_sha256": manifest_sha256,
            "enabled": False,
            "installed_by": actor,
            "updated_by": actor,
        },
    )
    previous = None
    if not created:
        if installation.enabled:
            raise ValidationError(
                "Disable the installed extension before changing its registered version."
            )
        previous = {
            "extension_version": installation.extension_version,
            "contract_version": installation.contract_version,
            "manifest_sha256": installation.manifest_sha256,
        }
        installation.extension_version = manifest["version"]
        installation.contract_version = manifest["contract_version"]
        installation.manifest_snapshot = manifest
        installation.manifest_sha256 = manifest_sha256
        installation.updated_by = actor
        installation.save()
    record_event(
        actor=actor,
        action="extension.installed",
        target=installation,
        details={
            "extension_key": extension_key,
            "extension_version": manifest["version"],
            "contract_version": manifest["contract_version"],
            "manifest_sha256": manifest_sha256,
            "created": created,
            "previous": previous,
        },
    )
    return installation


@transaction.atomic
def set_extension_enabled(*, extension_key: str, enabled: bool, actor):
    try:
        installation = ExtensionInstallation.objects.select_for_update().get(
            extension_key=extension_key
        )
    except ExtensionInstallation.DoesNotExist as exc:
        raise ValidationError("Install the extension before changing its enabled state.") from exc
    manifest = get_manifest(extension_key)
    if (
        installation.extension_version != manifest["version"]
        or installation.contract_version != manifest["contract_version"]
        or installation.manifest_sha256 != canonical_digest(manifest)
    ):
        raise ValidationError(
            "The installed extension does not match the current registry. Reinstall it disabled."
        )
    installation.enabled = enabled
    installation.updated_by = actor
    installation.save(update_fields=["enabled", "updated_by", "updated_at"])
    record_event(
        actor=actor,
        action="extension.enabled" if enabled else "extension.disabled",
        target=installation,
        details={
            "extension_key": extension_key,
            "extension_version": installation.extension_version,
            "contract_version": installation.contract_version,
            "manifest_sha256": installation.manifest_sha256,
        },
    )
    return installation


def _validated_installation(extension_key: str, contract_version: str):
    try:
        installation = ExtensionInstallation.objects.get(extension_key=extension_key)
    except ExtensionInstallation.DoesNotExist as exc:
        raise ValidationError(
            {"extension_key": "This extension is not installed or enabled."}
        ) from exc
    if not installation.enabled:
        raise ValidationError({"extension_key": "This extension is installed but disabled."})
    try:
        manifest = get_manifest(extension_key)
    except KeyError as exc:
        raise ValidationError(
            {"extension_key": "The requested extension is not in the server registry."}
        ) from exc
    if contract_version not in SUPPORTED_CONTRACT_VERSIONS:
        raise ValidationError(
            {
                "contract_version": (
                    f"Contract {contract_version} is not supported. "
                    f"Supported contracts: {', '.join(SUPPORTED_CONTRACT_VERSIONS)}."
                )
            }
        )
    expected_digest = canonical_digest(manifest)
    if (
        contract_version != manifest["contract_version"]
        or installation.contract_version != manifest["contract_version"]
        or installation.extension_version != manifest["version"]
        or installation.manifest_sha256 != expected_digest
    ):
        raise ValidationError(
            {
                "contract_version": (
                    "The installed extension contract or manifest is incompatible. "
                    "An administrator must disable and reinstall the registered version."
                )
            }
        )
    return installation, manifest


def _input_snapshot(
    *,
    incident,
    revision,
    extension_key: str,
    extension_version: str,
    contract_version: str,
    capability: str,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "ict-extension-input-v1",
        "extension_key": extension_key,
        "extension_version": extension_version,
        "contract_version": contract_version,
        "capability": capability,
        "scope": "incident_revision",
        "incident_id": str(incident.id),
        "source_revision": {
            "id": str(revision.id),
            "plan_id": str(revision.plan_id),
            "number": revision.number,
            "status": revision.status,
            "approved_at": revision.approved_at.isoformat(),
        },
        "parameters": deepcopy(parameters),
    }


def _record_failed_execution(
    *,
    installation,
    manifest,
    capability,
    capability_definition,
    incident,
    revision,
    input_snapshot,
    actor,
) -> ExtensionExecution:
    empty_result = {
        "schema_version": "ict-extension-failure-v1",
        "detail": "The optional extension failed without changing source records.",
    }
    execution = ExtensionExecution.objects.create(
        installation=installation,
        extension_key=manifest["key"],
        extension_version=manifest["version"],
        contract_version=manifest["contract_version"],
        capability=capability,
        capability_kind=capability_definition["kind"],
        incident=incident,
        source_revision=revision,
        input_snapshot=input_snapshot,
        input_sha256=canonical_digest(input_snapshot),
        result_snapshot=empty_result,
        result_sha256=canonical_digest(empty_result),
        output_classification=capability_definition["outputs"]["classification"],
        status=ExtensionExecution.Status.FAILED,
        failure_code="extension_execution_failed",
        failure_message="The optional extension failed. Core incident planning remains available.",
        created_by=actor,
    )
    record_event(
        actor=actor,
        action="extension.execution_failed",
        target=execution,
        details={
            "extension_key": execution.extension_key,
            "extension_version": execution.extension_version,
            "contract_version": execution.contract_version,
            "capability": execution.capability,
            "incident_id": str(execution.incident_id),
            "source_revision_id": str(execution.source_revision_id),
            "input_sha256": execution.input_sha256,
            "failure_code": execution.failure_code,
        },
    )
    return execution


def execute_extension(
    *,
    extension_key: str,
    contract_version: str,
    capability: str,
    incident,
    source_revision,
    parameters: dict[str, Any],
    actor,
) -> ExtensionExecution:
    installation, manifest = _validated_installation(extension_key, contract_version)
    try:
        capability_definition, handler = get_capability(extension_key, capability)
    except KeyError as exc:
        raise ValidationError(
            {"capability": "The requested capability is not declared by this extension."}
        ) from exc
    try:
        revision = PlanRevision.objects.select_related("plan__incident").get(pk=source_revision.pk)
    except PlanRevision.DoesNotExist as exc:
        raise ValidationError({"source_revision": "The source revision no longer exists."}) from exc
    if revision.plan.incident_id != incident.id:
        raise ValidationError(
            {"source_revision": "The source revision belongs to another incident."}
        )
    if revision.status != PlanRevision.Status.APPROVED:
        raise ValidationError(
            {"source_revision": "This extension requires an approved ICS-205 revision."}
        )
    snapshot = _input_snapshot(
        incident=incident,
        revision=revision,
        extension_key=extension_key,
        extension_version=manifest["version"],
        contract_version=contract_version,
        capability=capability,
        parameters=parameters,
    )
    try:
        result = handler(revision, deepcopy(parameters))
        if not isinstance(result, dict):
            raise TypeError("Extension handler returned a non-object result.")
        if result.get("schema_version") != capability_definition["outputs"]["schema"]:
            raise TypeError("Extension handler returned an incompatible output schema.")
        if len(canonical_json(result)) > 1_048_576:
            raise TypeError("Extension handler returned output above the 1 MiB contract limit.")
    except Exception:
        return _record_failed_execution(
            installation=installation,
            manifest=manifest,
            capability=capability,
            capability_definition=capability_definition,
            incident=incident,
            revision=revision,
            input_snapshot=snapshot,
            actor=actor,
        )
    execution = ExtensionExecution.objects.create(
        installation=installation,
        extension_key=extension_key,
        extension_version=manifest["version"],
        contract_version=contract_version,
        capability=capability,
        capability_kind=capability_definition["kind"],
        incident=incident,
        source_revision=revision,
        input_snapshot=snapshot,
        input_sha256=canonical_digest(snapshot),
        result_snapshot=result,
        result_sha256=canonical_digest(result),
        output_classification=capability_definition["outputs"]["classification"],
        status=ExtensionExecution.Status.COMPLETE,
        created_by=actor,
    )
    record_event(
        actor=actor,
        action="extension.executed",
        target=execution,
        details={
            "extension_key": execution.extension_key,
            "extension_version": execution.extension_version,
            "contract_version": execution.contract_version,
            "capability": execution.capability,
            "capability_kind": execution.capability_kind,
            "output_classification": execution.output_classification,
            "incident_id": str(execution.incident_id),
            "source_revision_id": str(execution.source_revision_id),
            "input_sha256": execution.input_sha256,
            "result_sha256": execution.result_sha256,
        },
    )
    return execution


def validate_execution_integrity(execution: ExtensionExecution) -> None:
    if canonical_digest(execution.input_snapshot) != execution.input_sha256:
        raise ValidationError("The retained extension input digest is invalid.")
    if canonical_digest(execution.result_snapshot) != execution.result_sha256:
        raise ValidationError("The retained extension result digest is invalid.")


def build_execution_package(execution: ExtensionExecution) -> bytes:
    if execution.status != ExtensionExecution.Status.COMPLETE:
        raise ValidationError("Only completed extension output can be exported.")
    validate_execution_integrity(execution)
    package = {
        "schema_version": "ict-extension-package-v1",
        "extension": {
            "key": execution.extension_key,
            "version": execution.extension_version,
            "contract_version": execution.contract_version,
            "capability": execution.capability,
            "capability_kind": execution.capability_kind,
            "manifest_sha256": execution.installation.manifest_sha256,
        },
        "source": {
            "incident_id": str(execution.incident_id),
            "revision_id": str(execution.source_revision_id),
            "revision_number": execution.input_snapshot["source_revision"]["number"],
            "input_sha256": execution.input_sha256,
        },
        "output": {
            "classification": execution.output_classification,
            "result_sha256": execution.result_sha256,
            "result": execution.result_snapshot,
        },
        "disclaimer": (
            "Synthetic extension-contract evidence only. "
            "This package is not an official ICS form or operational approval."
        ),
    }
    return canonical_json(package)
