"""jjjjjk12 추천 에이전트의 프롬프트 템플릿."""

from __future__ import annotations

from soma_agent.common.schemas import History
from soma_agent.jjjjjk12.schemas import InterestProfile, ScoredCandidate

PROFILE_SYSTEM_PROMPT = """
너는 수강 이력을 바탕으로 사용자의 관심사를 추출하는 추천 시스템 구성요소다.
반드시 JSON만 응답한다.
멘토 이름은 관심사, 키워드, 추천 근거로 사용하지 않는다.
""".strip()

REASON_SYSTEM_PROMPT = """
너는 추천 후보가 사용자 관심사와 맞는 이유를 설명하는 추천 시스템 구성요소다.
반드시 JSON만 응답한다.
멘토 이름은 추천 근거로 사용하지 않는다.
과장하지 말고 한 문장으로 짧게 설명한다.
""".strip()


def build_profile_user_prompt(
    histories: list[History],
    title_max_chars: int = 120,
    body_max_chars: int = 800,
) -> str:
    """관심사 추출용 사용자 프롬프트를 만든다."""

    history_text = build_history_prompt_text(
        histories,
        title_max_chars,
        body_max_chars,
    )
    return f"""
아래 수강 이력의 제목과 본문만 보고 관심사를 추출해줘.

{history_text}

응답 형식:
{{"summary": "1~2문장 관심사 요약", "keywords": ["키워드1", "키워드2"]}}
""".strip()


def build_history_prompt_text(
    histories: list[History],
    title_max_chars: int = 120,
    body_max_chars: int = 800,
) -> str:
    """수강 이력 목록을 프롬프트용 텍스트로 만든다."""

    lines = []
    for index, history in enumerate(histories, start=1):
        lines.extend(
            build_history_lines(index, history, title_max_chars, body_max_chars),
        )
    return "\n".join(lines)


def build_history_lines(
    index: int,
    history: History,
    title_max_chars: int,
    body_max_chars: int,
) -> list[str]:
    """수강 이력 하나를 프롬프트용 줄 목록으로 만든다."""

    title = truncate_text(history.title, title_max_chars)
    body = truncate_text(history.body, body_max_chars)
    lines = [f"{index}. 제목: {title}"]
    lines.append(f"   본문: {body}")
    return lines


def truncate_text(value: str | None, max_chars: int) -> str:
    """문자열을 최대 길이에 맞게 자른다."""

    text = (value or "").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip()


def build_reason_user_prompt(
    scored_candidate: ScoredCandidate,
    profile: InterestProfile,
) -> str:
    """추천 사유 생성용 사용자 프롬프트를 만든다."""

    candidate = scored_candidate.candidate
    return f"""
사용자 관심사: {profile.summary}
관심 키워드: {build_keyword_text(profile.keywords)}
추천 후보 제목: {candidate.title}
추천 후보 요약: {candidate.summary}
추천 점수: {scored_candidate.final_score:.3f}

응답 형식:
{{"reason": "추천 사유 한 문장"}}
""".strip()


def build_keyword_text(keywords: list[str]) -> str:
    """키워드 목록을 프롬프트용 문자열로 만든다."""

    if not keywords:
        return "없음"
    return ", ".join(keywords[:5])
