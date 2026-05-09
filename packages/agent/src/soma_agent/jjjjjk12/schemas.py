"""jjjjjk12 추천 에이전트 전용 스키마."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class InterestProfile:
    """수강 이력에서 추출한 관심사 요약."""

    summary: str
    keywords: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LectureCandidate:
    """VectorDB 검색에서 반환된 추천 후보."""

    mentoring_id: str
    title: str
    summary: str
    url: str
    score: float
    is_closed: bool = False


@dataclass(frozen=True)
class ScoredCandidate:
    """룰 기반 점수 정보를 포함한 추천 후보."""

    candidate: LectureCandidate
    final_score: float
    keyword_bonus: float = 0.0
