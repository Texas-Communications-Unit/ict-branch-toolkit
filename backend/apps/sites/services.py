from copy import deepcopy

from rest_framework.exceptions import ValidationError

from apps.plans.services import ensure_draft

from .models import RadioSite


def site_snapshot(site: RadioSite) -> dict:
    return {
        "site_id": str(site.id),
        "name": site.name,
        "description": site.description,
        "latitude": f"{site.latitude:.6f}",
        "longitude": f"{site.longitude:.6f}",
        "entered_coordinate": site.entered_coordinate,
        "coordinate_format": site.coordinate_format,
        "address": site.address,
        "source_identity": site.source_identity,
        "source_retrieved_at": (
            site.source_retrieved_at.isoformat() if site.source_retrieved_at else None
        ),
        "rings": [
            {
                "type": ring.ring_type,
                "radius_m": ring.radius_m,
                "label": ring.label,
            }
            for ring in site.rings.all().order_by("ring_type", "radius_m", "id")
        ],
    }


def freeze_revision_sites(revision) -> None:
    for assignment in revision.assignments.prefetch_related("site_links__site__rings"):
        for link in assignment.site_links.all():
            link.site_snapshot = site_snapshot(link.site)
            link.save(update_fields=["site_snapshot"])


def copy_revision_sites(source, assignment_map) -> None:
    from .models import SiteAssignment

    links = SiteAssignment.objects.filter(assignment__revision=source).select_related("site")
    SiteAssignment.objects.bulk_create(
        [
            SiteAssignment(site=link.site, assignment=assignment_map[link.assignment_id])
            for link in links
        ]
    )


def validate_site_link(site, assignment) -> None:
    ensure_draft(assignment.revision)
    if site.incident_id != assignment.revision.plan.incident_id:
        raise ValidationError("Site and assignment must belong to the same incident.")


def approved_site_records(revision) -> list[dict]:
    if revision.status != revision.Status.APPROVED:
        raise ValidationError("Official spatial exports require an approved revision.")
    records: dict[str, dict] = {}
    links = revision.assignments.prefetch_related("site_links").all().order_by("position", "id")
    for assignment in links:
        for link in assignment.site_links.all():
            if not link.site_snapshot:
                raise ValidationError("Approved site snapshot is missing.")
            snapshot = deepcopy(link.site_snapshot)
            site_id = snapshot["site_id"]
            record = records.setdefault(
                site_id,
                {**snapshot, "assignments": [], "assignment_ids": []},
            )
            record["assignments"].append(
                f"{assignment.position}. {assignment.function} — {assignment.channel_name}"
            )
            record["assignment_ids"].append(str(assignment.id))
    return sorted(records.values(), key=lambda item: (item["name"], item["site_id"]))
