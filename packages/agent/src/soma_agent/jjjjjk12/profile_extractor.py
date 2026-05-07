"""jjjjjk12 추천 에이전트의 관심사 프로필 추출."""

from __future__ import annotations

from soma_agent.common.schemas import History
from soma_agent.jjjjjk12.schemas import InterestProfile


KEYWORD_CANDIDATES = [
    "FastAPI",
    "Python",
    "백엔드",
    "API",
    "인증",
    "DB 연동",
    "배포",
    "AI",
    "LLM",
    "추천",
    "프론트엔드",
    "React",
]


class FallbackProfileExtractor:
    """LLM 없이 사용할 수 있는 규칙 기반 관심사 추출기."""

    def extract(self, histories: list[History]) -> InterestProfile:
        """수강 이력에서 관심사 프로필을 추출한다."""

        history_text = collect_history_text(histories)
        keywords = extract_keywords(history_text)
        summary = build_summary(keywords)
        return InterestProfile(summary, keywords)


def collect_history_text(histories: list[History]) -> str:
    """수강 이력의 제목과 본문을 하나의 문자열로 합친다."""

    parts = []
    for history in histories:
        parts.extend(get_history_text_parts(history))
    return " ".join(parts)


def get_history_text_parts(history: History) -> list[str]:
    """수강 이력 하나에서 제목과 본문만 꺼낸다."""

    result = []
    if history.title:
        result.append(history.title)
    if history.body:
        result.append(history.body)
    return result


def extract_keywords(text: str) -> list[str]:
    """수강 이력 텍스트에서 관심 키워드를 찾는다."""

    result = []
    lowered_text = text.lower()
    for keyword in KEYWORD_CANDIDATES:
        if keyword.lower() in lowered_text:
            result.append(keyword)
    return result


def build_summary(keywords: list[str]) -> str:
    """키워드 목록으로 관심사 요약문을 만든다."""

    if not keywords:
        return build_default_summary()
    keyword_text = ", ".join(keywords[:5])
    return f"{keyword_text} 주제에 관심이 있습니다."


def build_default_summary() -> str:
    """키워드가 없을 때 사용할 기본 관심사 요약문을 만든다."""

    return "수강 이력을 바탕으로 유사한 주제의 특강을 추천합니다."
