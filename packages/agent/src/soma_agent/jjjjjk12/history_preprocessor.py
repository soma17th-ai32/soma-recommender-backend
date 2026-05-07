"""jjjjjk12 추천 에이전트의 수강 이력 전처리."""

from __future__ import annotations

from soma_agent.common.schemas import History
from soma_agent.jjjjjk12.errors import EmptyHistoryError


def prepare_histories(histories: list[History]) -> list[History]:
    """추천 workflow에서 사용할 수강 이력을 정리한다."""

    filtered_histories = filter_usable_histories(histories)
    unique_histories = remove_duplicate_urls(filtered_histories)
    sorted_histories = sort_by_taken_at_desc(unique_histories)
    if not sorted_histories:
        raise EmptyHistoryError("사용 가능한 수강 이력이 없습니다.")
    return sorted_histories


def filter_usable_histories(histories: list[History]) -> list[History]:
    """URL과 제목/본문 중 하나가 있는 이력만 남긴다."""

    result = []
    for history in histories:
        if is_usable_history(history):
            result.append(history)
    return result


def is_usable_history(history: History) -> bool:
    """추천에 사용할 수 있는 수강 이력인지 확인한다."""

    has_url = bool(clean_text(history.url))
    has_title = bool(clean_text(history.title))
    has_body = bool(clean_text(history.body))
    return has_url and (has_title or has_body)


def remove_duplicate_urls(histories: list[History]) -> list[History]:
    """같은 URL을 가진 이력은 한 번만 남긴다."""

    result = []
    seen_urls = set()
    for history in histories:
        url = clean_text(history.url)
        if url in seen_urls:
            continue
        seen_urls.add(url)
        result.append(history)
    return result


def sort_by_taken_at_desc(histories: list[History]) -> list[History]:
    """수강 이력을 최신순으로 정렬한다."""

    return sorted(histories, key=get_taken_at_sort_key, reverse=True)


def get_taken_at_sort_key(history: History) -> str:
    """정렬에 사용할 수강 일시 값을 반환한다."""

    return clean_text(history.taken_at)


def clean_text(value: str | None) -> str:
    """문자열 앞뒤 공백을 제거한다."""

    if value is None:
        return ""
    return value.strip()
