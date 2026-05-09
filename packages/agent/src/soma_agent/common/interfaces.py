"""SOMA 에이전트가 공유하는 공통 인터페이스."""

from __future__ import annotations

from typing import Protocol

from soma_agent.common.schemas import RecommendationRequest, RecommendationResult


class RecommendationAgent(Protocol):
    """모든 추천 에이전트가 맞춰야 하는 공통 진입점."""

    def recommend(self, request: RecommendationRequest) -> RecommendationResult:
        """요청에 대한 추천 결과를 반환한다."""
        ...
