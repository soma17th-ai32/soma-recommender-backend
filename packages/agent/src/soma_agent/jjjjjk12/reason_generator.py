"""jjjjjk12 추천 에이전트의 추천 사유 생성."""

from __future__ import annotations

from soma_agent.jjjjjk12.schemas import InterestProfile
from soma_agent.jjjjjk12.schemas import ScoredCandidate


class FallbackReasonGenerator:
    """LLM 없이 사용할 수 있는 규칙 기반 추천 사유 생성기."""

    def generate(
        self,
        scored_candidate: ScoredCandidate,
        profile: InterestProfile,
    ) -> str:
        """추천 후보에 대한 짧은 추천 사유를 만든다."""

        keywords = find_matched_keywords(scored_candidate, profile)
        if keywords:
            return build_keyword_reason(keywords)
        return build_default_reason()


def find_matched_keywords(
    scored_candidate: ScoredCandidate,
    profile: InterestProfile,
) -> list[str]:
    """후보 제목/요약에 실제로 포함된 관심 키워드를 찾는다."""

    result = []
    candidate_text = build_candidate_text(scored_candidate)
    for keyword in profile.keywords:
        if is_keyword_in_text(keyword, candidate_text):
            result.append(keyword)
    return result


def build_candidate_text(scored_candidate: ScoredCandidate) -> str:
    """키워드 매칭에 사용할 후보 텍스트를 만든다."""

    candidate = scored_candidate.candidate
    return f"{candidate.title} {candidate.summary}".lower()


def is_keyword_in_text(keyword: str, text: str) -> bool:
    """관심 키워드가 후보 텍스트에 포함되는지 확인한다."""

    keyword = keyword.strip().lower()
    if not keyword:
        return False
    return keyword in text


def build_keyword_reason(keywords: list[str]) -> str:
    """관심 키워드 기반 추천 사유를 만든다."""

    keyword_text = ", ".join(keywords[:3])
    return f"{keyword_text} 관심 키워드와 주제가 유사합니다."


def build_default_reason() -> str:
    """기본 추천 사유를 만든다."""

    return "수강 이력에서 추출한 관심사와 주제가 유사합니다."
