"""jjjjjk12 추천 에이전트의 프롬프트 템플릿."""

from __future__ import annotations

from soma_agent.common.schemas import History


PROFILE_SYSTEM_PROMPT = """
너는 수강 이력을 바탕으로 사용자의 관심사를 추출하는 추천 시스템 구성요소다.
반드시 JSON만 응답한다.
멘토 이름은 관심사, 키워드, 추천 근거로 사용하지 않는다.
""".strip()


def build_profile_user_prompt(histories: list[History]) -> str:
    """관심사 추출용 사용자 프롬프트를 만든다."""

    history_text = build_history_prompt_text(histories)
    return f"""
아래 수강 이력의 제목과 본문만 보고 관심사를 추출해줘.

{history_text}

응답 형식:
{{"summary": "1~2문장 관심사 요약", "keywords": ["키워드1", "키워드2"]}}
""".strip()


def build_history_prompt_text(histories: list[History]) -> str:
    """수강 이력 목록을 프롬프트용 텍스트로 만든다."""

    lines = []
    for index, history in enumerate(histories, start=1):
        lines.extend(build_history_lines(index, history))
    return "\n".join(lines)


def build_history_lines(index: int, history: History) -> list[str]:
    """수강 이력 하나를 프롬프트용 줄 목록으로 만든다."""

    lines = [f"{index}. 제목: {history.title or ''}"]
    lines.append(f"   본문: {history.body or ''}")
    return lines
