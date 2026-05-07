"""jjjjjk12 추천 에이전트의 검색 쿼리 생성."""

from __future__ import annotations

from soma_agent.jjjjjk12.schemas import InterestProfile


def build_query_text(profile: InterestProfile) -> str:
    """관심사 프로필을 검색용 문장으로 만든다."""

    lines = [build_summary_line(profile)]
    if has_keywords(profile):
        lines.append(build_keyword_line(profile))
    return "\n".join(lines)


def build_summary_line(profile: InterestProfile) -> str:
    """관심사 요약 줄을 만든다."""

    return f"관심 요약: {profile.summary}"


def has_keywords(profile: InterestProfile) -> bool:
    """관심 키워드가 있는지 확인한다."""

    return bool(profile.keywords)


def build_keyword_line(profile: InterestProfile) -> str:
    """관심 키워드 줄을 만든다."""

    return f"핵심 키워드: {', '.join(profile.keywords)}"
