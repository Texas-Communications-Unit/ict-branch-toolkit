import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient


@pytest.fixture
def client():
    user = get_user_model().objects.create_user(username="location-search-test")
    api = APIClient()
    api.force_authenticate(user=user)
    return api


@pytest.mark.django_db
def test_local_decimal_coordinate_never_uses_external_provider(client):
    response = client.post(
        "/api/locations/resolve/",
        {"query": "33.214500, -97.133100", "external_lookup_allowed": False},
        format="json",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["resolution_method"] == "local_coordinate"
    assert payload["external_lookup_performed"] is False
    assert payload["results"][0]["crs"] == "EPSG:4326"
    assert payload["results"][0]["formats"]["decimal"] == "33.214500, -97.133100"


@pytest.mark.django_db
def test_google_style_url_is_parsed_locally_without_google_dependency(client):
    response = client.post(
        "/api/locations/resolve/",
        {
            "query": "https://www.google.com/maps/@33.2145,-97.1331,15z",
            "external_lookup_allowed": False,
        },
        format="json",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["resolution_method"] == "local_coordinate"
    assert payload["external_lookup_performed"] is False
    assert payload["results"][0]["latitude"] == 33.2145
    assert payload["results"][0]["longitude"] == -97.1331


@pytest.mark.django_db
@override_settings(ICT_GEOCODER_PROVIDER="apps.sites.geocoders.DeterministicTestGeocoder")
def test_external_lookup_requires_explicit_approval(client):
    response = client.post(
        "/api/locations/resolve/",
        {"query": "synthetic eoc", "external_lookup_allowed": False},
        format="json",
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["external_lookup_performed"] is False
    assert payload["results"] == []
    assert "not approved" in payload["blocked_reason"].lower()


@pytest.mark.django_db
@override_settings(ICT_GEOCODER_PROVIDER="apps.sites.geocoders.DeterministicTestGeocoder")
def test_intersection_results_include_locality_for_disambiguation(client):
    response = client.post(
        "/api/locations/resolve/",
        {"query": "Alpha Rd & Bravo St", "external_lookup_allowed": True},
        format="json",
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["resolution_method"] == "geocoder"
    assert payload["external_lookup_performed"] is True
    assert len(payload["results"]) == 2
    assert "Synthetic City, TX" in payload["results"][0]["label"]
    assert "Other Synthetic City, TX" in payload["results"][1]["label"]


@pytest.mark.django_db
def test_what3words_fails_closed_when_provider_is_not_approved(client):
    response = client.post(
        "/api/locations/resolve/",
        {"query": "///alpha.bravo.charlie", "external_lookup_allowed": True},
        format="json",
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["resolution_method"] == "what3words"
    assert payload["configured"] is False
    assert payload["external_lookup_performed"] is False
    assert payload["results"] == []


@pytest.mark.django_db
@override_settings(
    ICT_WHAT3WORDS_PROVIDER="apps.sites.what3words.DeterministicTestWhat3WordsProvider",
    ICT_APPROVED_WHAT3WORDS_PROVIDERS=[
        "apps.sites.what3words.DeterministicTestWhat3WordsProvider"
    ],
)
def test_approved_what3words_adapter_returns_normalized_synthetic_result(client):
    response = client.post(
        "/api/locations/resolve/",
        {"query": "///alpha.bravo.charlie", "external_lookup_allowed": True},
        format="json",
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["configured"] is True
    assert payload["external_lookup_performed"] is True
    assert payload["results"][0]["formats"]["decimal"] == "33.214500, -97.133100"
