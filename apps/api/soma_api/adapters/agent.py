from typing import Protocol

from soma_agent.common.errors import SomaAgentError
from soma_agent.common.interfaces import RecommendationAgent
from soma_agent.common.schemas import History, RecommendationRequest
from soma_agent.jjjjjk12.errors import (
    EmbeddingProviderError,
    EmptyHistoryError,
    NoRecommendationFoundError,
    ProfileExtractionError,
    ReasonGenerationError,
    VectorSearchError,
)
from soma_agent.jjjjjk12.factory import create_jjjjjk12_workflow

from soma_api.errors import ApiError
from soma_api.models import (
    AgentRecommendationResult,
    NormalizedHistory,
    RecommendationItem,
)

EMPTY_HISTORY = "EMPTY_HISTORY"
EMBEDDING_PROVIDER_FAILED = "EMBEDDING_PROVIDER_FAILED"
NO_RECOMMENDATION_FOUND = "NO_RECOMMENDATION_FOUND"
PROFILE_EXTRACTION_FAILED = "PROFILE_EXTRACTION_FAILED"
REASON_GENERATION_FAILED = "REASON_GENERATION_FAILED"
RECOMMENDATION_AGENT_FAILED = "RECOMMENDATION_AGENT_FAILED"
VECTOR_SEARCH_FAILED = "VECTOR_SEARCH_FAILED"


class RecommendationAgentAdapter(Protocol):
    def recommend(
        self,
        histories: list[NormalizedHistory],
        limit: int,
        request_id: str,
    ) -> AgentRecommendationResult: ...


class Jjjjjk12RecommendationAgentAdapter:
    def __init__(self, workflow: RecommendationAgent | None = None) -> None:
        self._workflow = workflow or create_jjjjjk12_workflow()

    def recommend(
        self,
        histories: list[NormalizedHistory],
        limit: int,
        request_id: str,
    ) -> AgentRecommendationResult:
        del request_id

        request = RecommendationRequest(
            histories=[
                History(
                    url=history.url,
                    title=history.title,
                    body=history.body,
                    mentor=history.mentor,
                    taken_at=history.taken_at.isoformat(),
                )
                for history in histories
            ],
            limit=limit,
        )

        try:
            result = self._workflow.recommend(request)
        except EmptyHistoryError as error:
            raise ApiError(EMPTY_HISTORY, "histories must not be empty", 400) from error
        except NoRecommendationFoundError as error:
            raise ApiError(
                NO_RECOMMENDATION_FOUND,
                "No recommendation candidates were found",
                400,
            ) from error
        except ProfileExtractionError as error:
            raise ApiError(
                PROFILE_EXTRACTION_FAILED,
                "Failed to extract recommendation profile",
                502,
            ) from error
        except ReasonGenerationError as error:
            raise ApiError(
                REASON_GENERATION_FAILED,
                "Failed to generate recommendation reasons",
                502,
            ) from error
        except EmbeddingProviderError as error:
            raise ApiError(
                EMBEDDING_PROVIDER_FAILED,
                "Failed to generate recommendation embedding",
                502,
            ) from error
        except VectorSearchError as error:
            raise ApiError(
                VECTOR_SEARCH_FAILED,
                "Failed to search recommendation candidates",
                503,
            ) from error
        except SomaAgentError as error:
            raise ApiError(
                RECOMMENDATION_AGENT_FAILED,
                "Recommendation agent failed",
                500,
            ) from error

        return AgentRecommendationResult(
            interest_summary=result.interest_summary,
            items=[
                RecommendationItem(
                    mentoring_id=item.mentoring_id,
                    title=item.title,
                    summary=item.summary,
                    url=item.url,
                    mentor=None,
                    score=item.score,
                    reason=item.reason,
                )
                for item in result.items
            ],
        )


class StubRecommendationAgentAdapter:
    def recommend(
        self,
        histories: list[NormalizedHistory],
        limit: int,
        request_id: str,
    ) -> AgentRecommendationResult:
        topics = [history.title for history in histories if history.title]
        if not topics:
            topics = [history.body[:40] for history in histories if history.body]
        interest_summary = "Interested in " + ", ".join(topics[:3])
        # TODO: Use actual agent implementation after packages are fully functional
        items = [
            RecommendationItem(
                mentoring_id=f"stub-{index + 1}",
                title=f"Recommended mentoring for {history.title or 'your learning history'}",
                summary="A deterministic stub recommendation for API contract testing.",
                url=f"https://example.com/recommendations/{index + 1}",
                mentor=history.mentor or "SOMA Mentor",
                score=max(0.1, 0.95 - (index * 0.05)),
                reason=f"Matches your history from {history.url}",
            )
            for index, history in enumerate(histories)
        ]

        return AgentRecommendationResult(
            interest_summary=interest_summary,
            items=items[:limit],
        )
