from fastapi.testclient import TestClient

from app import api as api_module
from app.api import create_api


def test_health_returns_db_and_provider_statuses(monkeypatch):
    async def db_ok() -> bool:
        return True

    monkeypatch.setattr(api_module, "check_database", db_ok)
    client = TestClient(create_api())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "db": "ok",
        "providers": {
            "fast_flights": "enabled",
            "atadi_web": "enabled",
            "atadi_rest": "disabled",
        },
    }


def test_health_returns_503_when_database_fails(monkeypatch):
    async def db_error() -> bool:
        return False

    monkeypatch.setattr(api_module, "check_database", db_error)
    client = TestClient(create_api())

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["db"] == "error"
