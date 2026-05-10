"""Upstage embedding API를 OpenAI 호환 client로 호출하는 adapter."""

from openai import OpenAI

from lecture_sync.models import LectureDetail
from lecture_sync.parser import build_embedding_text
from lecture_sync.settings import load_upstage_settings


def create_upstage_client(settings=None) -> OpenAI:
    """OpenAI 호환 클라이언트로 Upstage API client를 생성한다."""

    settings = settings or load_upstage_settings()
    return OpenAI(api_key=settings.api_key, base_url=settings.base_url)


def embed_text(text: str) -> list[float]:
    """Upstage embedding API로 텍스트를 벡터로 변환한다."""

    settings = load_upstage_settings()
    client = create_upstage_client(settings)
    # Upstage는 OpenAI embeddings API와 호환되는 응답 구조를 사용한다.
    response = client.embeddings.create(
        input=text,
        model=settings.embedding_model,
    )
    return response.data[0].embedding


def embed_lecture_detail(detail: LectureDetail) -> list[float]:
    """특강 제목과 설명만 사용해 저장용 문서 임베딩을 생성한다."""

    return embed_text(build_embedding_text(detail.title, detail.description))
