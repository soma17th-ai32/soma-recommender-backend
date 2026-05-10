"""jjjjjk12 추천 에이전트의 추천 사유 생성."""

from __future__ import annotations

from openai import OpenAI, OpenAIError
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel, ValidationError

from soma_agent.jjjjjk12.errors import ReasonGenerationError
from soma_agent.jjjjjk12.prompts import REASON_SYSTEM_PROMPT, build_reason_user_prompt
from soma_agent.jjjjjk12.schemas import InterestProfile, ScoredCandidate


class ReasonGenerationResponse(BaseModel):
    """LLM 추천 사유 응답 형식을 검증한다."""

    reason: str


class LlmReasonGenerator:
    """LLM을 사용해 추천 사유를 생성한다."""

    def __init__(self, client: OpenAI, model: str, fallback=None) -> None:
        self.client = client
        self.model = model
        self.fallback = fallback or FallbackReasonGenerator()

    def generate(
        self,
        scored_candidate: ScoredCandidate,
        profile: InterestProfile,
    ) -> str:
        """LLM으로 추천 사유를 생성하고 실패 시 fallback을 사용한다."""

        try:
            content = self._request_reason(scored_candidate, profile)
            return parse_reason_response(content)
        except ReasonGenerationError:
            return self.fallback.generate(scored_candidate, profile)

    def _request_reason(
        self,
        scored_candidate: ScoredCandidate,
        profile: InterestProfile,
    ) -> str:
        """LLM에 추천 사유 생성 요청을 보낸다."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=build_reason_messages(scored_candidate, profile),
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content or ""
        except (OpenAIError, IndexError, AttributeError) as error:
            raise ReasonGenerationError("LLM 추천 사유 생성에 실패했습니다.") from error


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


def build_reason_messages(
    scored_candidate: ScoredCandidate,
    profile: InterestProfile,
) -> list[ChatCompletionMessageParam]:
    """LLM chat completion 요청 메시지를 만든다."""

    return [
        {"role": "system", "content": REASON_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": build_reason_user_prompt(scored_candidate, profile),
        },
    ]


def parse_reason_response(content: str) -> str:
    """LLM JSON 응답을 추천 사유 문자열로 변환한다."""

    data = load_reason_json(content)
    reason = data.reason.strip()
    if not reason:
        raise ReasonGenerationError("LLM 추천 사유가 비어 있습니다.")
    return reason


def load_reason_json(content: str) -> ReasonGenerationResponse:
    """LLM 응답 문자열을 Pydantic 모델로 검증한다."""

    try:
        return ReasonGenerationResponse.model_validate_json(content)
    except ValidationError as error:
        raise ReasonGenerationError("LLM 추천 사유 응답 형식이 올바르지 않습니다.") from error


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
