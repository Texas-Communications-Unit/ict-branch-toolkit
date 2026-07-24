import pytest
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from rest_framework.throttling import ScopedRateThrottle, UserRateThrottle

from config.exceptions import handle_exception


def auth_header(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {"HTTP_AUTHORIZATION": f"Token {token.key}"}


@pytest.mark.django_db
def test_responses_carry_secure_headers(client):
    user = get_user_model().objects.create_user("hardening-reader", password="safe-test-password")
    response = client.get("/api/incidents/", **auth_header(user))
    assert response.status_code == 200
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["X-Frame-Options"] == "DENY"
    assert response["Referrer-Policy"] == "same-origin"


@pytest.mark.django_db
def test_health_check_is_not_authenticated_but_still_carries_secure_headers(client):
    response = client.get("/api/health/")
    assert response.status_code == 200
    assert response["X-Content-Type-Options"] == "nosniff"


@pytest.mark.django_db
def test_token_endpoint_is_throttled_separately_from_general_api_traffic(client, monkeypatch):
    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "auth", "2/min")
    get_user_model().objects.create_user("throttle-user", password="safe-test-password")
    payload = {"username": "throttle-user", "password": "wrong-password"}

    first = client.post("/api/auth/token/", payload)
    second = client.post("/api/auth/token/", payload)
    third = client.post("/api/auth/token/", payload)

    assert first.status_code == 400
    assert second.status_code == 400
    assert third.status_code == 429
    assert "Retry-After" in third


@pytest.mark.django_db
def test_general_api_throttling_is_independent_of_the_auth_scope(client, monkeypatch):
    monkeypatch.setitem(UserRateThrottle.THROTTLE_RATES, "user", "2/min")
    user = get_user_model().objects.create_user("throttled-reader", password="safe-test-password")
    headers = auth_header(user)

    first = client.get("/api/incidents/", **headers)
    second = client.get("/api/incidents/", **headers)
    third = client.get("/api/incidents/", **headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429


def test_unhandled_exception_returns_a_generic_body_without_leaking_details():
    class BoomError(Exception):
        pass

    response = handle_exception(BoomError("sensitive internal detail"), {"request": None})

    assert response.status_code == 500
    assert response.data == {"detail": "An unexpected error occurred."}
    assert "sensitive internal detail" not in str(response.data)


@pytest.mark.django_db
def test_drf_exception_responses_are_returned_unmodified(client):
    response = client.get("/api/incidents/")
    assert response.status_code == 401
    assert "detail" in response.json()
