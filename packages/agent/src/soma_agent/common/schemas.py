"""SOMA 에이전트가 공유하는 공통 입출력 스키마."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class History:
    """Chrome Extension이 수집한 멘토링 수강 이력."""

    url: str
    title: str | None = None
    body: str | None = None
    mentor: str | None = None
    taken_at: str | None = None


@dataclass(frozen=True)
class RecommendationRequest:
    """Backend가 추천 에이전트에 전달하는 공통 입력."""

    histories: list[History]
    limit: int = 10


@dataclass(frozen=True)
class RecommendationItem:
    """추천 에이전트가 반환하는 최종 추천 항목."""

    mentoring_id: str
    title: str
    summary: str
    url: str
    score: float
    reason: str


@dataclass(frozen=True)
class RecommendationResult:
    """추천 에이전트가 반환하는 공통 추천 결과."""

    interest_summary: str
    items: list[RecommendationItem]
