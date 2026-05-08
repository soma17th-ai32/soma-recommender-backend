from typing import Protocol

from soma_api.models import (
    AgentRecommendationResult,
    NormalizedHistory,
    RecommendationItem,
)


class RecommendationAgentAdapter(Protocol):
    def recommend(
        self,
        histories: list[NormalizedHistory],
        limit: int,
        request_id: str,
    ) -> AgentRecommendationResult: ...


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
