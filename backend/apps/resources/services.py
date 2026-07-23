import hashlib
import json

from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.audit.services import record_event

from .models import (
    ConventionalChannel,
    ResourceImport,
    ResourceRelease,
    ResourceSource,
    TrunkedTalkgroup,
)


class ReferenceApprovalRequired(ValidationError):
    default_code = "approval_required"


def _payload_digest(raw_payload: dict) -> str:
    canonical = json.dumps(raw_payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def reference_is_approved(source: dict, release: dict) -> bool:
    if not source["source_type"].startswith("cisa_"):
        return True
    candidate = {
        "source_type": source["source_type"],
        "version": release["version"],
        "authoritative_url": source.get("authoritative_url", ""),
        "content_sha256": release["content_sha256"],
    }
    return candidate in settings.ICT_APPROVED_REFERENCE_IMPORTS


def preview_import(validated_data: dict) -> dict:
    source = validated_data["source"]
    release = validated_data["release"]
    exists = ResourceRelease.objects.filter(
        source__slug=source["slug"], version=release["version"]
    ).exists()
    return {
        "valid": not exists,
        "dry_run": True,
        "approval_required": not reference_is_approved(source, release),
        "would_create": {
            "sources": int(not ResourceSource.objects.filter(slug=source["slug"]).exists()),
            "releases": int(not exists),
            "conventional_channels": len(validated_data.get("conventional_channels", [])),
            "trunked_talkgroups": len(validated_data.get("trunked_talkgroups", [])),
        },
        "errors": (
            []
            if not exists
            else [
                {
                    "path": "release.version",
                    "code": "duplicate",
                    "message": "This source release already exists and cannot be replaced.",
                }
            ]
        ),
    }


@transaction.atomic
def apply_import(*, validated_data: dict, raw_payload: dict, actor) -> ResourceImport:
    source_data = validated_data["source"]
    release_data = validated_data["release"]
    if not reference_is_approved(source_data, release_data):
        raise ReferenceApprovalRequired(
            "This CISA release has not passed the configured human approval gate."
        )

    source, created = ResourceSource.objects.get_or_create(
        slug=source_data["slug"], defaults=source_data
    )
    if not created and any(
        getattr(source, field) != source_data.get(field, "")
        for field in ("name", "source_type", "authoritative_url")
    ):
        raise ValidationError(
            {"source": "The source slug already exists with different provenance metadata."}
        )
    if ResourceRelease.objects.filter(source=source, version=release_data["version"]).exists():
        raise ValidationError(
            {"release": "This source release already exists and cannot be replaced."}
        )

    release = ResourceRelease.objects.create(source=source, imported_by=actor, **release_data)
    conventional = [
        ConventionalChannel(release=release, **record)
        for record in validated_data.get("conventional_channels", [])
    ]
    talkgroups = [
        TrunkedTalkgroup(release=release, **record)
        for record in validated_data.get("trunked_talkgroups", [])
    ]
    ConventionalChannel.objects.bulk_create(conventional)
    TrunkedTalkgroup.objects.bulk_create(talkgroups)
    import_record = ResourceImport.objects.create(
        release=release,
        imported_by=actor,
        payload_sha256=_payload_digest(raw_payload),
        conventional_count=len(conventional),
        talkgroup_count=len(talkgroups),
    )
    record_event(
        actor=actor,
        action="resource_release.imported",
        target=release,
        details={
            "source": source.slug,
            "version": release.version,
            "payload_sha256": import_record.payload_sha256,
            "conventional_count": len(conventional),
            "talkgroup_count": len(talkgroups),
        },
    )
    return import_record
