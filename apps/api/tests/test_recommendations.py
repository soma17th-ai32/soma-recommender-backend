from fastapi.testclient import TestClient

from soma_api.adapters.agent import RecommendationAgentAdapter
from soma_api.app import create_app
from soma_api.dependencies import get_recommendation_service
from soma_api.models import AgentRecommendationResult, NormalizedHistory
from soma_api.services.recommendation_service import RecommendationService
from soma_api.storage.ttl import InMemoryTTLHistoryStore


class EmptyRecommendationAgentAdapter:
    def recommend(
        self,
        histories: list[NormalizedHistory],
        limit: int,
        request_id: str,
    ) -> AgentRecommendationResult:
        return AgentRecommendationResult(interest_summary="No matches", items=[])


def make_client(
    adapter: RecommendationAgentAdapter | None = None,
) -> tuple[TestClient, InMemoryTTLHistoryStore]:
    app = create_app()
    store = InMemoryTTLHistoryStore()
    service = RecommendationService(store, adapter or EmptyDefaultAdapter())
    app.dependency_overrides[get_recommendation_service] = lambda: service
    return TestClient(app), store


class EmptyDefaultAdapter:
    def recommend(
        self,
        histories: list[NormalizedHistory],
        limit: int,
        request_id: str,
    ) -> AgentRecommendationResult:
        from soma_api.adapters.agent import StubRecommendationAgentAdapter

        return StubRecommendationAgentAdapter().recommend(histories, limit, request_id)


def valid_payload() -> dict[str, object]:
    return {
        "histories": [
            {
                "url": " https://example.com/history/1 ",
                "title": " FastAPI basics ",
                "body": " Build APIs ",
                "mentor": " Mentor A ",
            },
            {
                "url": " https://example.com/history/1 ",
                "title": " Duplicate should be deduped ",
            },
            {
                "url": "https://example.com/history/2",
                "body": "Backend architecture",
            },
        ],
        "limit": 1,
    }


def test_recommendations_success_returns_response_and_stores_normalized_history() -> None:
    client, store = make_client()

    response = client.post("/v1/recommendations", json=valid_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["request_id"].startswith("req_")
    assert body["interest_summary"]
    assert len(body["items"]) == 1
    assert body["items"][0]["mentoring_id"] == "stub-1"

    stored = store.get(body["request_id"])
    assert stored is not None
    assert len(stored.histories) == 2
    assert stored.histories[0].url == "https://example.com/history/1"
    assert stored.histories[0].title == "FastAPI basics"
    assert stored.histories[0].body == "Build APIs"
    assert stored.histories[0].taken_at is not None


def test_empty_histories_returns_400_empty_history() -> None:
    client, _ = make_client()

    response = client.post("/v1/recommendations", json={"histories": []})

    assert response.status_code == 400
    body = response.json()
    assert body["request_id"].startswith("req_")
    assert body["error"]["code"] == "EMPTY_HISTORY"


def test_missing_title_and_body_returns_400_invalid_history_payload() -> None:
    client, _ = make_client()

    response = client.post(
        "/v1/recommendations",
        json={"histories": [{"url": "https://example.com/history", "title": "  "}]},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["request_id"].startswith("req_")
    assert body["error"]["code"] == "INVALID_HISTORY_PAYLOAD"


def test_empty_agent_result_returns_400_no_recommendation_found() -> None:
    client, _ = make_client(EmptyRecommendationAgentAdapter())

    response = client.post(
        "/v1/recommendations",
        json={"histories": [{"url": "https://example.com/history", "title": "FastAPI"}]},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["request_id"].startswith("req_")
    assert body["error"]["code"] == "NO_RECOMMENDATION_FOUND"


def test_missing_histories_returns_422_invalid_request_schema() -> None:
    client, _ = make_client()

    response = client.post("/v1/recommendations", json={})

    assert response.status_code == 422
    body = response.json()
    assert body["request_id"].startswith("req_")
    assert body["error"] == {
        "code": "INVALID_REQUEST_SCHEMA",
        "message": "Request body does not match the required schema",
    }


def test_histories_not_array_returns_422_invalid_request_schema() -> None:
    client, _ = make_client()

    response = client.post("/v1/recommendations", json={"histories": "invalid"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST_SCHEMA"


def test_history_missing_url_returns_422_invalid_request_schema() -> None:
    client, _ = make_client()

    response = client.post("/v1/recommendations", json={"histories": [{"title": "FastAPI"}]})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST_SCHEMA"


def test_invalid_taken_at_returns_422_invalid_request_schema() -> None:
    client, _ = make_client()

    response = client.post(
        "/v1/recommendations",
        json={
            "histories": [
                {
                    "url": "https://example.com/history",
                    "title": "FastAPI",
                    "taken_at": "not-a-date",
                }
            ]
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST_SCHEMA"


def test_invalid_limit_returns_422_invalid_request_schema() -> None:
    client, _ = make_client()

    response = client.post(
        "/v1/recommendations",
        json={
            "histories": [{"url": "https://example.com/history", "title": "FastAPI"}],
            "limit": 0,
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST_SCHEMA"


def test_malformed_json_returns_422_invalid_request_schema() -> None:
    client, _ = make_client()

    response = client.post(
        "/v1/recommendations",
        content="{not-json",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["request_id"].startswith("req_")
    assert body["error"]["code"] == "INVALID_REQUEST_SCHEMA"
