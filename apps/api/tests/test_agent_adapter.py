from datetime import UTC, datetime

import pytest
from soma_agent.common.schemas import RecommendationItem as AgentRecommendationItem
from soma_agent.common.schemas import RecommendationRequest as AgentRecommendationRequest
from soma_agent.common.schemas import RecommendationResult as AgentRecommendationResult
from soma_agent.jjjjjk12.errors import (
    EmbeddingProviderError,
    NoRecommendationFoundError,
    VectorSearchError,
)

from soma_api.adapters.agent import (
    EMBEDDING_PROVIDER_FAILED,
    NO_RECOMMENDATION_FOUND,
    VECTOR_SEARCH_FAILED,
    Jjjjjk12RecommendationAgentAdapter,
)
from soma_api.errors import ApiError
from soma_api.models import NormalizedHistory


class CapturingWorkflow:
    def __init__(self) -> None:
        self.request: AgentRecommendationRequest | None = None

    def recommend(self, request: AgentRecommendationRequest) -> AgentRecommendationResult:
        self.request = request
        return AgentRecommendationResult(
            interest_summary="백엔드 API에 관심이 높습니다.",
            items=[
                AgentRecommendationItem(
                    mentoring_id="10268",
                    title="실전 FastAPI 백엔드 설계",
                    summary="FastAPI 기반 API 구조와 DB 연동을 다룹니다.",
                    url="https://example.com/lecture/10268",
                    score=0.91,
                    reason="수강 이력의 백엔드 관심사와 연결됩니다.",
                )
            ],
        )


class FailingWorkflow:
    def __init__(self, error: Exception) -> None:
        self._error = error

    def recommend(self, request: AgentRecommendationRequest) -> AgentRecommendationResult:
        raise self._error


def test_jjjjjk12_adapter_maps_api_request_to_agent_request() -> None:
    workflow = CapturingWorkflow()
    adapter = Jjjjjk12RecommendationAgentAdapter(workflow)
    taken_at = datetime(2026, 5, 1, 10, 0, tzinfo=UTC)

    result = adapter.recommend(
        [
            NormalizedHistory(
                url="https://example.com/history/1",
                title="FastAPI basics",
                body="Build APIs",
                mentor="Mentor A",
                taken_at=taken_at,
            )
        ],
        limit=7,
        request_id="req_test",
    )

    assert workflow.request is not None
    assert workflow.request.limit == 7
    assert len(workflow.request.histories) == 1
    assert workflow.request.histories[0].url == "https://example.com/history/1"
    assert workflow.request.histories[0].title == "FastAPI basics"
    assert workflow.request.histories[0].body == "Build APIs"
    assert workflow.request.histories[0].mentor == "Mentor A"
    assert workflow.request.histories[0].taken_at == taken_at.isoformat()
    assert result.interest_summary == "백엔드 API에 관심이 높습니다."
    assert result.items[0].mentoring_id == "10268"
    assert result.items[0].mentor is None


@pytest.mark.parametrize(
    ("agent_error", "code", "status_code"),
    [
        (
            NoRecommendationFoundError("empty"),
            NO_RECOMMENDATION_FOUND,
            400,
        ),
        (
            EmbeddingProviderError("embedding failed"),
            EMBEDDING_PROVIDER_FAILED,
            502,
        ),
        (
            VectorSearchError("vector failed"),
            VECTOR_SEARCH_FAILED,
            503,
        ),
    ],
)
def test_jjjjjk12_adapter_maps_agent_errors_to_api_errors(
    agent_error: Exception,
    code: str,
    status_code: int,
) -> None:
    adapter = Jjjjjk12RecommendationAgentAdapter(FailingWorkflow(agent_error))

    with pytest.raises(ApiError) as exc_info:
        adapter.recommend(
            [
                NormalizedHistory(
                    url="https://example.com/history/1",
                    title="FastAPI basics",
                    taken_at=datetime(2026, 5, 1, 10, 0, tzinfo=UTC),
                )
            ],
            limit=10,
            request_id="req_test",
        )

    assert exc_info.value.code == code
    assert exc_info.value.status_code == status_code
