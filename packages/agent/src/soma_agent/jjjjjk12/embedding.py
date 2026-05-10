"""jjjjjk12 추천 에이전트의 Upstage 임베딩 연동."""

from __future__ import annotations

from openai import OpenAI, OpenAIError

from soma_agent.jjjjjk12.errors import EmbeddingProviderError

DEFAULT_UPSTAGE_BASE_URL = "https://api.upstage.ai/v1/solar"
DEFAULT_UPSTAGE_EMBEDDING_MODEL = "solar-embedding-1-large-query"


class UpstageEmbeddingClient:
    """OpenAI 호환 방식으로 Upstage embedding API를 호출하는 client."""

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_UPSTAGE_EMBEDDING_MODEL,
        base_url: str = DEFAULT_UPSTAGE_BASE_URL,
        timeout_seconds: float = 20.0,
    ) -> None:
        self.model = model
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout_seconds,
        )

    def embed(self, text: str) -> list[float]:
        """검색 query text를 임베딩 벡터로 변환한다."""

        text = normalize_text(text)
        if not text:
            raise EmbeddingProviderError("임베딩할 텍스트가 비어 있습니다.")
        response = self._create_embedding(text)
        return parse_embedding_response(response)

    def _create_embedding(self, text: str):
        """OpenAI client로 Upstage embedding API를 호출한다."""

        try:
            return self.client.embeddings.create(model=self.model, input=text)
        except OpenAIError as error:
            raise EmbeddingProviderError("Upstage 임베딩 호출에 실패했습니다.") from error


def parse_embedding_response(response) -> list[float]:
    """Upstage 응답에서 첫 번째 embedding을 꺼낸다."""

    try:
        embedding = response.data[0].embedding
    except (AttributeError, IndexError, TypeError) as error:
        raise EmbeddingProviderError("Upstage 임베딩 응답 형식이 올바르지 않습니다.") from error
    return normalize_embedding(embedding)


def normalize_embedding(embedding: object) -> list[float]:
    """embedding 값을 float list로 정규화한다."""

    if not isinstance(embedding, list):
        raise EmbeddingProviderError("Upstage 임베딩 값이 list가 아닙니다.")
    return [float(value) for value in embedding]


def normalize_text(text: str) -> str:
    """임베딩 요청에 사용할 텍스트를 정리한다."""

    return text.strip()
