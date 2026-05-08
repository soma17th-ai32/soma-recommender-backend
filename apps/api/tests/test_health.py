from fastapi.testclient import TestClient

from soma_api.app import app


def test_health_returns_ok() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_returns_dependency_statuses() -> None:
    client = TestClient(app)

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "dependencies": {
            "ttl_storage": "ok",
            "vectordb": "stub",
            "llm": "stub",
            "embedding": "stub",
        },
    }
