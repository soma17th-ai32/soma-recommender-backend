from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class LectureListItem:
    """목록 페이지에서 확인한 접수 가능 특강의 최소 정보."""

    source_id: str
    title: str
    detail_url: str
    status: str | None = None
    receipt_period: str | None = None
    event_date: str | None = None
    author: str | None = None
    registered_at: str | None = None


@dataclass(frozen=True)
class LectureBase:
    """특강 상세 본문을 가진 데이터 모델의 공통 필드."""

    source_id: str
    title: str
    description: str


@dataclass(frozen=True)
class LectureDetail(LectureBase):
    """상세 페이지에서 수집한 임베딩/저장 대상 특강 정보."""

    detail_url: str
    content_hash: str


@dataclass(frozen=True)
class LectureData(LectureBase):
    """목록 메타데이터와 상세 본문을 합친 DB 저장 단위."""

    detail_url: str
    receipt_period: str | None
    event_date: str | None
    author: str | None
    registered_at: str | None
    content_hash: str


@dataclass(frozen=True)
class LectureRecord(LectureBase):
    """DB에 이미 저장되어 있다고 가정하는 기존 특강 row 정보."""

    status: str
    content_hash: str
    last_seen_at: datetime | None


@dataclass(frozen=True)
class SyncLectureResult:
    """한 번의 특강 동기화 작업 결과 요약."""

    fetched_count: int
    inserted_count: int
    updated_count: int
    activated_count: int
    inactivated_count: int
    embedding_pending_count: int


@dataclass(frozen=True)
class SomaSettings:
    """소마 사이트 크롤링에 필요한 환경변수 기반 설정."""

    base_url: str
    login_url: str
    lecture_list_url: str
    username: str
    password: str
    timeout_seconds: float = 20.0
    user_agent: str = "Mozilla/5.0 (compatible; SOMA-Recommender/0.1)"
    max_pages: int | None = None
    detail_refresh_interval_seconds: int | None = None


@dataclass(frozen=True)
class UpstageSettings:
    """Upstage 임베딩 API 호출에 필요한 설정."""

    api_key: str
    base_url: str = "https://api.upstage.ai/v1"
    embedding_model: str = "embedding-passage"
