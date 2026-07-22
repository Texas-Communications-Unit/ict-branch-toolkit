import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_health_reports_database(client):
    response = client.get(reverse("health"))
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["database"] in {"sqlite", "postgresql"}
