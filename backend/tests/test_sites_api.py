import json

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.authtoken.models import Token

from apps.incidents.models import Incident, OperationalPeriod
from apps.plans.models import Assignment, ICS205Plan, PlanRevision
from apps.sites.coordinates import CoordinateError, coordinate_formats, parse_coordinate
from apps.sites.models import RadioSite, SiteAssignment


def auth_header(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {"HTTP_AUTHORIZATION": f"Token {token.key}"}


def planning_context():
    admin = get_user_model().objects.create_superuser(
        "site-admin", "site-admin@example.invalid", "safe-test-password"
    )
    incident = Incident.objects.create(
        name="Synthetic Spatial Exercise", incident_number="SYN-GIS", created_by=admin
    )
    period = OperationalPeriod.objects.create(
        incident=incident,
        name="Operational Period 1",
        starts_at="2026-07-23T08:00:00Z",
        ends_at="2026-07-23T20:00:00Z",
        created_by=admin,
    )
    plan = ICS205Plan.objects.create(
        incident=incident,
        operational_period=period,
        title="Synthetic ICS-205",
        created_by=admin,
    )
    revision = PlanRevision.objects.create(plan=plan, number=1, created_by=admin)
    assignment = Assignment.objects.create(
        revision=revision,
        position=1,
        function="Command",
        channel_name="SYN CALL",
        assignment="Synthetic exercise",
        rx_frequency_hz=155_001_000,
        tx_frequency_hz=155_001_000,
        resource_snapshot={"type": "incident", "name": "SYN CALL"},
    )
    return admin, incident, revision, assignment


@pytest.mark.parametrize(
    ("text", "expected_format"),
    [
        ("33.214500, -97.133100", "decimal"),
        ("33° 12.8700′ N, 97° 07.9860′ W", "ddm"),
        ("33° 12′ 52.20″ N, 97° 07′ 59.16″ W", "dms"),
    ],
)
def test_coordinate_parser_accepts_documented_angular_formats(text, expected_format):
    parsed = parse_coordinate(text)
    assert parsed.input_format == expected_format
    assert parsed.latitude == pytest.approx(33.2145, abs=0.00001)
    assert parsed.longitude == pytest.approx(-97.1331, abs=0.00001)


def test_mgrs_round_trip_and_coordinate_boundaries():
    encoded = coordinate_formats(33.2145, -97.1331)["mgrs"]
    parsed = parse_coordinate(encoded)
    assert parsed.input_format == "mgrs"
    assert parsed.latitude == pytest.approx(33.2145, abs=0.00002)
    assert parsed.longitude == pytest.approx(-97.1331, abs=0.00002)
    with pytest.raises(CoordinateError, match="Latitude"):
        parse_coordinate("91, -97")
    with pytest.raises(CoordinateError, match="less than 60"):
        parse_coordinate("33 61 N, 97 01 W")


@pytest.mark.django_db
def test_site_ring_link_approval_snapshot_and_official_exports(client):
    admin, incident, revision, assignment = planning_context()
    headers = auth_header(admin)
    created = client.post(
        "/api/radio-sites/",
        {
            "incident": str(incident.id),
            "name": "Synthetic Command Site",
            "coordinate_text": "33° 12′ 52.20″ N, 97° 07′ 59.16″ W",
            "description": "Synthetic test fixture",
        },
        content_type="application/json",
        **headers,
    )
    assert created.status_code == 201, created.content
    site_id = created.json()["id"]
    assert created.json()["coordinate_format"] == "dms"
    assert created.json()["coordinate_formats"]["mgrs"]

    ring = client.post(
        "/api/manual-rings/",
        {
            "site": site_id,
            "ring_type": "operational",
            "radius_m": 8_000,
            "label": "Synthetic operational ring",
        },
        content_type="application/json",
        **headers,
    )
    assert ring.status_code == 201, ring.content
    linked = client.post(
        "/api/site-assignments/",
        {"site": site_id, "assignment": str(assignment.id)},
        content_type="application/json",
        **headers,
    )
    assert linked.status_code == 201, linked.content

    approved = client.post(f"/api/plan-revisions/{revision.id}/approve/", **headers)
    assert approved.status_code == 200, approved.content
    link = SiteAssignment.objects.get()
    assert link.site_snapshot["rings"][0]["radius_m"] == 8_000
    assert link.site_snapshot["latitude"] == "33.214500"

    changed = client.patch(
        f"/api/radio-sites/{site_id}/",
        {"latitude": "33.500000", "longitude": "-97.500000"},
        content_type="application/json",
        **headers,
    )
    assert changed.status_code == 200, changed.content
    immutable_link = client.delete(f"/api/site-assignments/{link.id}/", **headers)
    assert immutable_link.status_code == 400

    for export_format, content_type in [
        ("geojson", "application/geo+json"),
        ("csv", "text/csv"),
        ("kml", "application/vnd.google-earth.kml+xml"),
        ("map", "image/svg+xml"),
    ]:
        response = client.get(f"/api/spatial-exports/{revision.id}/{export_format}/", **headers)
        assert response.status_code == 200, response.content
        assert response["Content-Type"].startswith(content_type)
        assert b"Planning decision support only" in response.content
        assert b"No external basemap data is included" in response.content
        assert b"33.214500" in response.content
        assert b"33.500000" not in response.content

    copied = client.post(f"/api/plan-revisions/{revision.id}/copy/", **headers)
    assert copied.status_code == 201, copied.content
    draft = PlanRevision.objects.get(pk=copied.json()["id"])
    assert SiteAssignment.objects.filter(assignment__revision=draft).count() == 1
    assert not SiteAssignment.objects.get(assignment__revision=draft).site_snapshot


@pytest.mark.django_db
def test_bbox_uses_spatial_location_and_cross_incident_links_are_rejected(client):
    admin, incident, revision, assignment = planning_context()
    headers = auth_header(admin)
    site = RadioSite.objects.create(
        incident=incident,
        name="Synthetic Indexed Site",
        latitude="33.214500",
        longitude="-97.133100",
        entered_coordinate="33.214500, -97.133100",
        created_by=admin,
    )
    assert RadioSite._meta.get_field("location").spatial_index is True
    included = client.get(f"/api/radio-sites/?incident={incident.id}&bbox=-98,33,-97,34", **headers)
    assert included.status_code == 200, included.content
    assert [item["id"] for item in included.json()["results"]] == [str(site.id)]
    excluded = client.get(f"/api/radio-sites/?incident={incident.id}&bbox=-96,33,-95,34", **headers)
    assert excluded.json()["results"] == []

    other_incident = Incident.objects.create(name="Other Synthetic Incident", created_by=admin)
    other_site = RadioSite.objects.create(
        incident=other_incident,
        name="Other Synthetic Site",
        latitude="32.0",
        longitude="-96.0",
        created_by=admin,
    )
    rejected = client.post(
        "/api/site-assignments/",
        {"site": str(other_site.id), "assignment": str(assignment.id)},
        content_type="application/json",
        **headers,
    )
    assert rejected.status_code == 400

    draft_export = client.get(f"/api/spatial-exports/{revision.id}/geojson/", **headers)
    assert draft_export.status_code == 400


@pytest.mark.django_db
@override_settings(ICT_GEOCODER_PROVIDER="apps.sites.geocoders.DeterministicTestGeocoder")
def test_replaceable_geocoder_hook_is_deterministic(client):
    admin, incident, _, _ = planning_context()
    response = client.post(
        "/api/geocoder/search/",
        {"address": "Synthetic EOC"},
        content_type="application/json",
        **auth_header(admin),
    )
    assert response.status_code == 200
    assert response.json()["provider"] == "synthetic-test-provider"
    assert response.json()["results"][0]["label"] == "Synthetic EOC (test fixture)"
    created = client.post(
        "/api/radio-sites/",
        {
            "incident": str(incident.id),
            "name": "Synthetic Geocoded Site",
            "coordinate_text": "33.214500, -97.133100",
            "coordinate_format": "address",
            "address": "Synthetic EOC (test fixture)",
            "source_identity": "synthetic-test-provider",
            "source_retrieved_at": "2026-07-23T20:00:00Z",
        },
        content_type="application/json",
        **auth_header(admin),
    )
    assert created.status_code == 201, created.content
    assert created.json()["coordinate_format"] == "address"
    assert created.json()["source_identity"] == "synthetic-test-provider"


@pytest.mark.django_db
def test_geojson_is_valid_and_deterministic(client):
    admin, incident, revision, assignment = planning_context()
    site = RadioSite.objects.create(
        incident=incident,
        name="Synthetic Site",
        latitude="33.214500",
        longitude="-97.133100",
        created_by=admin,
    )
    SiteAssignment.objects.create(site=site, assignment=assignment)
    client.post(f"/api/plan-revisions/{revision.id}/approve/", **auth_header(admin))
    first = client.get(f"/api/spatial-exports/{revision.id}/geojson/", **auth_header(admin)).content
    second = client.get(
        f"/api/spatial-exports/{revision.id}/geojson/", **auth_header(admin)
    ).content
    assert first == second
    assert json.loads(first)["features"][0]["geometry"]["type"] == "Point"
