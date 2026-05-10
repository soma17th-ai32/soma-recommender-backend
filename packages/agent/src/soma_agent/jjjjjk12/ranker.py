"""jjjjjk12 추천 에이전트의 랭킹 로직."""

from __future__ import annotations

from soma_agent.jjjjjk12.errors import NoRecommendationFoundError
from soma_agent.jjjjjk12.schemas import LectureCandidate, ScoredCandidate


def rank_candidates(
    candidates: list[LectureCandidate],
    limit: int,
) -> list[ScoredCandidate]:
    """후보를 점수순으로 정렬하고 Top-K만 남긴다."""

    if not candidates:
        raise NoRecommendationFoundError("추천 가능한 후보가 없습니다.")
    scored_candidates = score_candidates(candidates)
    sorted_candidates = sort_candidates(scored_candidates)
    return take_top_k(sorted_candidates, limit)


def score_candidates(
    candidates: list[LectureCandidate],
) -> list[ScoredCandidate]:
    """후보 목록에 최종 점수를 부여한다."""

    result = []
    for candidate in candidates:
        result.append(score_candidate(candidate))
    return result


def score_candidate(candidate: LectureCandidate) -> ScoredCandidate:
    """후보 하나에 최종 점수를 부여한다."""

    return ScoredCandidate(candidate, candidate.score)


def sort_candidates(
    candidates: list[ScoredCandidate],
) -> list[ScoredCandidate]:
    """점수화된 후보를 최종 점수 기준으로 정렬한다."""

    return sorted(candidates, key=get_final_score, reverse=True)


def take_top_k(
    candidates: list[ScoredCandidate],
    limit: int,
) -> list[ScoredCandidate]:
    """상위 K개 후보만 반환한다."""

    return candidates[:limit]


def get_final_score(candidate: ScoredCandidate) -> float:
    """정렬에 사용할 최종 점수를 반환한다."""

    return candidate.final_score
