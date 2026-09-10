import pytest
from django.contrib.auth import get_user_model

from apps.fcc_data.nifog import build_nifog_match_index
from apps.resources.models import ConventionalChannel, ResourceRelease, ResourceSource

pytestmark = pytest.mark.django_db


def make_release(*, user, source, version, status=ResourceRelease.Status.EFFECTIVE):
    return ResourceRelease.objects.create(
        source=source,
        version=version,
        effective_status=status,
        content_sha256=(version.encode().hex() + "0" * 64)[:64],
        document_title=f"Synthetic NIFOG {version}",
        publisher="Synthetic CISA fixture",
        imported_by=user,
    )


def make_channel(*, release, identifier, rx, tx=None, active=True):
    return ConventionalChannel.objects.create(
        release=release,
        identifier=identifier,
        name=f"Synthetic {identifier}",
        rx_frequency_hz=rx,
        tx_frequency_hz=tx,
        mode=ConventionalChannel.Mode.ANALOG_FM,
        is_active=active,
    )


def test_exact_integer_hz_match_preserves_multiple_identifiers_and_roles():
    user = get_user_model().objects.create_user(username="nifog-test-user")
    source = ResourceSource.objects.create(
        slug="synthetic-nifog",
        name="Synthetic NIFOG source",
        source_type=ResourceSource.Type.CISA_NIFOG,
        authoritative_url="https://example.invalid/nifog",
    )
    release = make_release(user=user, source=source, version="SYN-2")
    make_channel(
        release=release,
        identifier="SYN-A",
        rx=159_472_500,
        tx=159_472_500,
    )
    make_channel(
        release=release,
        identifier="SYN-B",
        rx=159_472_500,
        tx=151_000_000,
    )

    matches = build_nifog_match_index([159_472_500])[159_472_500]

    assert [match["identifier"] for match in matches] == ["SYN-A", "SYN-B"]
    assert matches[0]["matched_roles"] == ["rx", "tx"]
    assert matches[1]["matched_roles"] == ["rx"]
    assert matches[0]["release"]["version"] == "SYN-2"
    assert matches[0]["source"]["slug"] == "synthetic-nifog"


def test_nearby_frequency_does_not_float_match():
    user = get_user_model().objects.create_user(username="nifog-near-test")
    source = ResourceSource.objects.create(
        slug="synthetic-nifog-near",
        name="Synthetic NIFOG near-match source",
        source_type=ResourceSource.Type.CISA_NIFOG,
    )
    release = make_release(user=user, source=source, version="SYN-1")
    make_channel(release=release, identifier="SYN-EXACT", rx=159_472_500)

    assert build_nifog_match_index([159_472_499]) == {}


def test_latest_effective_release_is_selected_per_source():
    user = get_user_model().objects.create_user(username="nifog-version-test")
    source = ResourceSource.objects.create(
        slug="synthetic-nifog-versioned",
        name="Synthetic versioned NIFOG",
        source_type=ResourceSource.Type.CISA_NIFOG,
    )
    old = make_release(user=user, source=source, version="SYN-OLD")
    make_channel(release=old, identifier="OLD-ID", rx=159_472_500)
    latest = make_release(user=user, source=source, version="SYN-LATEST")
    make_channel(release=latest, identifier="LATEST-ID", rx=159_472_500)

    matches = build_nifog_match_index([159_472_500])[159_472_500]

    assert [match["identifier"] for match in matches] == ["LATEST-ID"]
    assert matches[0]["release"]["version"] == "SYN-LATEST"


def test_draft_superseded_and_inactive_channels_are_not_enriched():
    user = get_user_model().objects.create_user(username="nifog-disabled-test")
    draft_source = ResourceSource.objects.create(
        slug="synthetic-nifog-draft",
        name="Synthetic draft NIFOG",
        source_type=ResourceSource.Type.CISA_NIFOG,
    )
    draft = make_release(
        user=user,
        source=draft_source,
        version="SYN-DRAFT",
        status=ResourceRelease.Status.DRAFT,
    )
    make_channel(release=draft, identifier="DRAFT-ID", rx=159_472_500)

    effective_source = ResourceSource.objects.create(
        slug="synthetic-nifog-inactive",
        name="Synthetic inactive NIFOG",
        source_type=ResourceSource.Type.CISA_NIFOG,
    )
    effective = make_release(user=user, source=effective_source, version="SYN-ACTIVE")
    make_channel(
        release=effective,
        identifier="INACTIVE-ID",
        rx=159_472_500,
        active=False,
    )

    assert build_nifog_match_index([159_472_500]) == {}
