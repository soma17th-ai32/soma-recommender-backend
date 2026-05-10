"""SOMA 특강 수집 결과를 DB 상태와 임베딩 상태로 동기화하는 서비스 계층."""

from datetime import UTC, datetime

import psycopg

from lecture_sync.crawler import (
    create_soma_session,
    fetch_available_lecture_list,
    fetch_lecture_data,
    is_session_alive,
    login_soma_site,
)
from lecture_sync.models import LectureListItem, LectureRecord, SomaSettings, SyncLectureResult
from lecture_sync.parser import needs_embedding_update
from lecture_sync.repository import (
    get_existing_lectures,
    insert_lecture,
    mark_lecture_active,
    mark_lectures_inactive,
    update_lecture,
    update_lecture_embedding,
    update_lecture_list_metadata,
    update_lecture_seen,
)
from lecture_sync.settings import load_database_url, load_soma_settings


def sync_lecture() -> SyncLectureResult:
    """소마 특강 목록 수집부터 DB 상태 갱신까지 수행하는 메인 진입점."""

    # 1. 프로젝트 루트 .env와 환경변수에서 소마 접속 설정을 읽는다.
    settings = load_soma_settings()

    # 2. 같은 로그인 쿠키를 유지할 HTTP session을 만들고 사용 후 정리한다.
    with create_soma_session(settings) as session:
        # 3. 현재 session으로 특강 목록에 접근할 수 없으면 로그인한다.
        if not is_session_alive(session, settings):
            login_soma_site(session, settings)

        # 4. 접수 가능 상태의 특강 목록을 모든 페이지에서 수집한다.
        available_lectures = fetch_available_lecture_list(session, settings)

        # 5. 수집 결과를 기준으로 신규/수정/비활성화/재활성화 대상을 한 DB connection에서 처리한다.
        with psycopg.connect(load_database_url()) as conn:
            return refresh_lecture_status(available_lectures, session, settings, conn)


def refresh_lecture_status(
    available_lectures: list[LectureListItem],
    session,
    settings: SomaSettings,
    conn,
) -> SyncLectureResult:
    """수집된 접수 가능 목록을 기준으로 DB 상태와 임베딩 갱신 대상을 계산한다."""

    existing_records = get_existing_lectures(conn)
    existing_by_id = {lecture.source_id: lecture for lecture in existing_records}
    available_ids = {lecture.source_id for lecture in available_lectures}
    existing_ids = set(existing_by_id)

    inserted_count = 0
    updated_count = 0
    activated_count = 0
    embedding_pending_count = 0

    # 현재 접수 가능 목록에서 사라진 기존 특강은 추천 대상에서 제외되도록 비활성화한다.
    missing_ids = existing_ids - available_ids
    inactivated_count = mark_lectures_inactive(conn, missing_ids)

    for lecture in available_lectures:
        existing = existing_by_id.get(lecture.source_id)

        # 이전 sync에서 비활성화된 특강이 다시 목록에 보이면 active로 복구한다.
        if existing is not None and existing.status == "inactive":
            mark_lecture_active(conn, lecture.source_id)
            activated_count += 1

        # 비용 절감 옵션이 켜진 경우, 최근 확인한 기존 row는 상세 호출을 건너뛴다.
        if existing is not None and should_skip_detail_refresh(existing, settings):
            update_lecture_list_metadata(conn, lecture)
            continue

        # 신규 특강은 상세 본문까지 수집한 뒤 DB row와 embedding을 함께 만든다.
        if existing is None:
            lecture_data = fetch_lecture_data(session, lecture, settings)
            insert_lecture(conn, lecture_data)
            embedding_pending_count += update_lecture_embedding(conn, lecture_data)
            inserted_count += 1
            continue

        lecture_data = fetch_lecture_data(session, lecture, settings)
        # 제목이나 설명이 바뀐 경우에만 기존 embedding을 버리고 새 embedding을 저장한다.
        if needs_embedding_update(existing.content_hash, lecture_data.content_hash):
            update_lecture(conn, lecture_data)
            embedding_pending_count += update_lecture_embedding(conn, lecture_data)
            updated_count += 1
            continue

        # 본문은 그대로지만 목록 메타데이터와 마지막 발견 시각은 최신 상태로 맞춘다.
        update_lecture_seen(conn, lecture_data)

    return SyncLectureResult(
        fetched_count=len(available_lectures),
        inserted_count=inserted_count,
        updated_count=updated_count,
        activated_count=activated_count,
        inactivated_count=inactivated_count,
        embedding_pending_count=embedding_pending_count,
    )


def should_skip_detail_refresh(existing: LectureRecord, settings: SomaSettings) -> bool:
    """설정된 refresh interval 안에 이미 본 기존 row는 상세 재조회를 건너뛴다."""

    interval_seconds = settings.detail_refresh_interval_seconds
    if interval_seconds is None or interval_seconds <= 0:
        return False
    if existing.last_seen_at is None or not existing.content_hash:
        return False

    last_seen_at = existing.last_seen_at
    # PostgreSQL timestamp가 naive datetime으로 들어와도 UTC 기준으로 비교한다.
    if last_seen_at.tzinfo is None:
        last_seen_at = last_seen_at.replace(tzinfo=UTC)

    elapsed_seconds = (datetime.now(UTC) - last_seen_at).total_seconds()
    return elapsed_seconds < interval_seconds
