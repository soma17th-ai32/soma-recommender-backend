"""jjjjjk12 추천 에이전트의 필터링 룰."""

from __future__ import annotations

from soma_agent.common.schemas import History
from soma_agent.jjjjjk12.schemas import LectureCandidate


def filter_recommendable_candidates(
    candidates: list[LectureCandidate],
    histories: list[History],
) -> list[LectureCandidate]:
    """추천 가능한 후보만 남긴다."""

    candidates = remove_closed_candidates(candidates)
    taken_urls = build_taken_urls(histories)
    return remove_taken_candidates(candidates, taken_urls)


def remove_closed_candidates(
    candidates: list[LectureCandidate],
) -> list[LectureCandidate]:
    """마감된 후보를 제외한다."""

    result = []
    for candidate in candidates:
        if candidate.is_closed:
            continue
        result.append(candidate)
    return result


def remove_taken_candidates(
    candidates: list[LectureCandidate],
    taken_urls: set[str],
) -> list[LectureCandidate]:
    """이미 수강한 URL과 같은 후보를 제외한다."""

    result = []
    for candidate in candidates:
        if candidate.url in taken_urls:
            continue
        result.append(candidate)
    return result


def build_taken_urls(histories: list[History]) -> set[str]:
    """수강 이력 URL 집합을 만든다."""

    result = set()
    for history in histories:
        result.add(history.url)
    return result
