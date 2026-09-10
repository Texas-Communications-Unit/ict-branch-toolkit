from collections import defaultdict

from django.db.models import Q

from apps.resources.models import ConventionalChannel, ResourceRelease, ResourceSource


def selected_effective_nifog_releases() -> list[ResourceRelease]:
    """Return the newest effective NIFOG release for each configured NIFOG source."""
    releases = (
        ResourceRelease.objects.select_related("source")
        .filter(
            source__source_type=ResourceSource.Type.CISA_NIFOG,
            effective_status=ResourceRelease.Status.EFFECTIVE,
        )
        .order_by("source_id", "-imported_at", "-version")
    )
    selected: dict[object, ResourceRelease] = {}
    for release in releases:
        selected.setdefault(release.source_id, release)
    return list(selected.values())


def build_nifog_match_index(frequencies_hz) -> dict[int, list[dict]]:
    frequencies = sorted({int(value) for value in frequencies_hz if value is not None})
    if not frequencies:
        return {}

    releases = selected_effective_nifog_releases()
    if not releases:
        return {}

    channels = (
        ConventionalChannel.objects.select_related("release", "release__source")
        .filter(release__in=releases, is_active=True)
        .filter(Q(rx_frequency_hz__in=frequencies) | Q(tx_frequency_hz__in=frequencies))
        .order_by("release__source__slug", "release__version", "identifier", "id")
    )

    index: dict[int, list[dict]] = defaultdict(list)
    for channel in channels:
        for frequency in frequencies:
            roles = []
            if channel.rx_frequency_hz == frequency:
                roles.append("rx")
            if channel.tx_frequency_hz == frequency:
                roles.append("tx")
            if not roles:
                continue
            release = channel.release
            source = release.source
            index[frequency].append(
                {
                    "identifier": channel.identifier,
                    "name": channel.name,
                    "matched_roles": roles,
                    "channel_rx_frequency_hz": channel.rx_frequency_hz,
                    "channel_tx_frequency_hz": channel.tx_frequency_hz,
                    "source": {
                        "slug": source.slug,
                        "name": source.name,
                        "authoritative_url": source.authoritative_url,
                    },
                    "release": {
                        "id": str(release.id),
                        "version": release.version,
                        "released_on": release.released_on.isoformat()
                        if release.released_on
                        else None,
                        "document_title": release.document_title,
                        "publisher": release.publisher,
                        "retrieved_on": release.retrieved_on.isoformat()
                        if release.retrieved_on
                        else None,
                        "content_sha256": release.content_sha256,
                    },
                }
            )
    return dict(index)


def matches_for_frequency(frequency_hz: int) -> list[dict]:
    return build_nifog_match_index([frequency_hz]).get(int(frequency_hz), [])
