import psycopg

from apps.api.lecture_sync.crawler import (
    create_soma_session,
    fetch_available_lecture_list,
    fetch_lecture_data,
    is_session_alive,
    login_soma_site,
)
from apps.api.lecture_sync.models import LectureListItem, SomaSettings, SyncLectureResult
from apps.api.lecture_sync.parser import needs_embedding_update
from apps.api.lecture_sync.repository import (
    get_existing_lectures,
    insert_lecture,
    mark_lecture_active,
    mark_lectures_inactive,
    queue_embedding_update,
    update_lecture,
    update_lecture_seen,
)
from apps.api.lecture_sync.settings import load_soma_settings
from apps.api.lecture_sync.settings import load_database_url


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

    missing_ids = existing_ids - available_ids
    inactivated_count = mark_lectures_inactive(conn, missing_ids)

    for lecture in available_lectures:
        existing = existing_by_id.get(lecture.source_id)
        if existing is not None and existing.status == "inactive":
            mark_lecture_active(conn, lecture.source_id)
            activated_count += 1

        if existing is None:
            lecture_data = fetch_lecture_data(session, lecture, settings)
            insert_lecture(conn, lecture_data)
            embedding_pending_count += queue_embedding_update(conn, lecture_data)
            inserted_count += 1
            continue

        lecture_data = fetch_lecture_data(session, lecture, settings)
        if needs_embedding_update(existing.content_hash, lecture_data.content_hash):
            update_lecture(conn, lecture_data)
            embedding_pending_count += queue_embedding_update(conn, lecture_data)
            updated_count += 1
            continue

        update_lecture_seen(conn, lecture_data)

    return SyncLectureResult(
        fetched_count=len(available_lectures),
        inserted_count=inserted_count,
        updated_count=updated_count,
        activated_count=activated_count,
        inactivated_count=inactivated_count,
        embedding_pending_count=embedding_pending_count,
    )
