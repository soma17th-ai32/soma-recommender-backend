"""jjjjjk12 추천 에이전트의 관심사 프로필 추출."""

from __future__ import annotations

from openai import OpenAI, OpenAIError
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel, Field, ValidationError

from soma_agent.common.schemas import History
from soma_agent.jjjjjk12.errors import ProfileExtractionError
from soma_agent.jjjjjk12.prompts import PROFILE_SYSTEM_PROMPT, build_profile_user_prompt
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


class ProfileExtractionResponse(BaseModel):
    """LLM 관심사 추출 응답 형식을 검증한다."""

    summary: str
    keywords: list[str] = Field(default_factory=list)


class LlmProfileExtractor:
    """LLM을 사용해 수강 이력에서 관심사를 추출한다."""

    def __init__(
        self,
        client: OpenAI,
        model: str,
        title_max_chars: int = 120,
        body_max_chars: int = 800,
        fallback=None,
    ) -> None:
        self.client = client
        self.model = model
        self.title_max_chars = title_max_chars
        self.body_max_chars = body_max_chars
        self.fallback = fallback or FallbackProfileExtractor()

    def extract(self, histories: list[History]) -> InterestProfile:
        """LLM으로 관심사 프로필을 추출하고 실패 시 fallback을 사용한다."""

        try:
            content = self._request_profile(histories)
            return parse_profile_response(content)
        except ProfileExtractionError:
            return self.fallback.extract(histories)

    def _request_profile(self, histories: list[History]) -> str:
        """LLM에 관심사 추출 요청을 보낸다."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self._build_messages(histories),
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content or ""
        except (OpenAIError, IndexError, AttributeError) as error:
            raise ProfileExtractionError("LLM 관심사 추출에 실패했습니다.") from error

    def _build_messages(self, histories: list[History]) -> list[ChatCompletionMessageParam]:
        """설정된 길이 제한을 적용해 LLM 메시지를 만든다."""

        return build_profile_messages(
            histories,
            self.title_max_chars,
            self.body_max_chars,
        )


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


def build_profile_messages(
    histories: list[History],
    title_max_chars: int = 120,
    body_max_chars: int = 800,
) -> list[ChatCompletionMessageParam]:
    """LLM chat completion 요청 메시지를 만든다."""

    return [
        {"role": "system", "content": PROFILE_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": build_profile_user_prompt(histories, title_max_chars, body_max_chars),
        },
    ]


def parse_profile_response(content: str) -> InterestProfile:
    """LLM JSON 응답을 관심사 프로필로 변환한다."""

    data = load_profile_json(content)
    summary = normalize_summary(data.summary)
    keywords = normalize_keywords(data.keywords)
    if not summary:
        raise ProfileExtractionError("LLM 관심사 요약이 비어 있습니다.")
    return InterestProfile(summary, keywords)


def load_profile_json(content: str) -> ProfileExtractionResponse:
    """LLM 응답 문자열을 Pydantic 모델로 검증한다."""

    try:
        return ProfileExtractionResponse.model_validate_json(content)
    except ValidationError as error:
        raise ProfileExtractionError("LLM 응답 형식이 올바르지 않습니다.") from error


def normalize_summary(value: str) -> str:
    """LLM 요약 값을 문자열로 정리한다."""

    return value.strip()


def normalize_keywords(value: list[str]) -> list[str]:
    """LLM 키워드 값을 문자열 목록으로 정리한다."""

    return [keyword.strip() for keyword in value if keyword.strip()]


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
