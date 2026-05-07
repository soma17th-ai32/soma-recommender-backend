"""jjjjjk12 추천 workflow 생성."""

from __future__ import annotations

from openai import OpenAI

from soma_agent.jjjjjk12.embedding import UpstageEmbeddingClient
from soma_agent.jjjjjk12.profile_extractor import LlmProfileExtractor
from soma_agent.jjjjjk12.reason_generator import FallbackReasonGenerator
from soma_agent.jjjjjk12.settings import Jjjjjk12AgentSettings
from soma_agent.jjjjjk12.settings import load_jjjjjk12_settings
from soma_agent.jjjjjk12.vector_store import PgvectorLectureSearchClient
from soma_agent.jjjjjk12.workflow import Jjjjjk12RecommendationWorkflow


def create_jjjjjk12_workflow(
    settings: Jjjjjk12AgentSettings | None = None,
) -> Jjjjjk12RecommendationWorkflow:
    """환경설정을 사용해 jjjjjk12 추천 workflow를 생성한다."""

    settings = settings or load_jjjjjk12_settings()
    return Jjjjjk12RecommendationWorkflow(
        profile_extractor=create_profile_extractor(settings),
        embedding_client=create_embedding_client(settings),
        vector_search_client=create_vector_search_client(settings),
        reason_generator=FallbackReasonGenerator(),
    )


def create_profile_extractor(settings: Jjjjjk12AgentSettings) -> LlmProfileExtractor:
    """LLM 관심사 추출기를 생성한다."""

    client = OpenAI(
        api_key=settings.upstage_api_key,
        base_url=settings.upstage_base_url,
        timeout=settings.timeout_seconds,
    )
    return LlmProfileExtractor(client, settings.upstage_chat_model)


def create_embedding_client(settings: Jjjjjk12AgentSettings) -> UpstageEmbeddingClient:
    """Upstage embedding client를 생성한다."""

    return UpstageEmbeddingClient(
        api_key=settings.upstage_api_key,
        model=settings.upstage_embedding_model,
        base_url=settings.upstage_base_url,
        timeout_seconds=settings.timeout_seconds,
    )


def create_vector_search_client(
    settings: Jjjjjk12AgentSettings,
) -> PgvectorLectureSearchClient:
    """pgvector 검색 client를 생성한다."""

    return PgvectorLectureSearchClient(settings.database_url)
