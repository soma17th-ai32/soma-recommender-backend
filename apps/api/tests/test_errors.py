from fastapi import Body
from fastapi.testclient import TestClient
from pydantic import BaseModel

from soma_api.app import create_app


class DummyPayload(BaseModel):
    name: str


def test_request_validation_error_returns_error_envelope() -> None:
    app = create_app()

    @app.post("/test/schema-validation")
    async def schema_validation(payload: DummyPayload = Body(...)) -> dict[str, str]:
        return {"name": payload.name}

    client = TestClient(app)

    response = client.post("/test/schema-validation", json={})

    assert response.status_code == 422
    body = response.json()
    assert body["request_id"].startswith("req_")
    assert body["error"] == {
        "code": "INVALID_REQUEST_SCHEMA",
        "message": "Request body does not match the required schema",
    }


def test_framework_http_error_returns_error_envelope() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.get("/missing")

    assert response.status_code == 404
    body = response.json()
    assert body["request_id"].startswith("req_")
    assert body["error"] == {
        "code": "HTTP_ERROR",
        "message": "Not Found",
    }
