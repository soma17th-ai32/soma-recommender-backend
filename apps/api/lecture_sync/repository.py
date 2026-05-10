"""lectures 테이블을 읽고 쓰는 PostgreSQL/pgvector repository."""

from lecture_sync.embedding import embed_text
from lecture_sync.models import LectureData, LectureListItem, LectureRecord
from lecture_sync.parser import build_embedding_text


def get_existing_lectures(conn) -> list[LectureRecord]:
    """DB에서 기존 특강 목록을 조회한다."""

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT source_id, title, description, status, content_hash, last_seen_at
            FROM lectures
            """
        )
        return [
            LectureRecord(
                source_id=row[0],
                title=row[1],
                description=row[2],
                status=row[3],
                content_hash=row[4],
                last_seen_at=row[5],
            )
            for row in cur.fetchall()
        ]


def insert_lecture(conn, lecture: LectureData) -> None:
    """신규 특강을 active 상태로 DB에 저장한다."""

    with conn.cursor() as cur:
        # source_id는 SOMA qustnrSn이므로 같은 특강이 다시 들어오면 active row로 갱신한다.
        cur.execute(
            """
            INSERT INTO lectures (
                source_id,
                title,
                description,
                detail_url,
                status,
                receipt_period,
                event_date,
                author,
                registered_at,
                content_hash,
                last_seen_at,
                updated_at
            )
            VALUES (
                %(source_id)s,
                %(title)s,
                %(description)s,
                %(detail_url)s,
                'active',
                %(receipt_period)s,
                %(event_date)s,
                %(author)s,
                %(registered_at)s,
                %(content_hash)s,
                now(),
                now()
            )
            ON CONFLICT (source_id) DO UPDATE SET
                title = EXCLUDED.title,
                description = EXCLUDED.description,
                detail_url = EXCLUDED.detail_url,
                status = 'active',
                receipt_period = EXCLUDED.receipt_period,
                event_date = EXCLUDED.event_date,
                author = EXCLUDED.author,
                registered_at = EXCLUDED.registered_at,
                content_hash = EXCLUDED.content_hash,
                last_seen_at = now(),
                updated_at = now()
            """,
            _lecture_params(lecture),
        )


def update_lecture(conn, lecture: LectureData) -> None:
    """내용이 변경된 기존 특강 row를 갱신하고 임베딩을 비운다."""

    with conn.cursor() as cur:
        # content_hash가 바뀐 row는 이전 embedding이 낡았으므로 NULL 처리 후 다시 저장한다.
        cur.execute(
            """
            UPDATE lectures
            SET title = %(title)s,
                description = %(description)s,
                detail_url = %(detail_url)s,
                status = 'active',
                receipt_period = %(receipt_period)s,
                event_date = %(event_date)s,
                author = %(author)s,
                registered_at = %(registered_at)s,
                content_hash = %(content_hash)s,
                embedding = NULL,
                embedding_updated_at = NULL,
                last_seen_at = now(),
                updated_at = now()
            WHERE source_id = %(source_id)s
            """,
            _lecture_params(lecture),
        )


def update_lecture_seen(conn, lecture: LectureData) -> None:
    """본문이 그대로인 특강의 목록 메타데이터와 마지막 발견 시각만 갱신한다."""

    with conn.cursor() as cur:
        # 상세 본문은 이미 비교된 상태이므로 embedding 관련 컬럼은 건드리지 않는다.
        cur.execute(
            """
            UPDATE lectures
            SET status = 'active',
                receipt_period = %(receipt_period)s,
                event_date = %(event_date)s,
                author = %(author)s,
                registered_at = %(registered_at)s,
                last_seen_at = now(),
                updated_at = now()
            WHERE source_id = %(source_id)s
            """,
            _lecture_params(lecture),
        )


def update_lecture_list_metadata(conn, lecture: LectureListItem) -> None:
    """상세 본문을 다시 보지 않는 fast-path에서 목록 메타데이터만 갱신한다."""

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE lectures
            SET status = 'active',
                receipt_period = %(receipt_period)s,
                event_date = %(event_date)s,
                author = %(author)s,
                registered_at = %(registered_at)s,
                last_seen_at = now(),
                updated_at = now()
            WHERE source_id = %(source_id)s
            """,
            {
                "source_id": lecture.source_id,
                "receipt_period": lecture.receipt_period,
                "event_date": lecture.event_date,
                "author": lecture.author,
                "registered_at": lecture.registered_at,
            },
        )


def mark_lectures_inactive(conn, source_ids: set[str]) -> int:
    """이번 목록에 없는 기존 특강을 접수 불가능 상태로 변경한다."""

    if not source_ids:
        return 0

    with conn.cursor() as cur:
        # 이미 inactive인 row는 rowcount에서 제외해 실제 변경 건수만 반환한다.
        cur.execute(
            """
            UPDATE lectures
            SET status = 'inactive',
                updated_at = now()
            WHERE source_id = ANY(%s)
              AND status <> 'inactive'
            """,
            (list(source_ids),),
        )
        return cur.rowcount


def mark_lecture_active(conn, source_id: str) -> None:
    """이전에 비활성화된 특강이 다시 보이면 접수 가능 상태로 복구한다."""

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE lectures
            SET status = 'active',
                last_seen_at = now(),
                updated_at = now()
            WHERE source_id = %s
            """,
            (source_id,),
        )


def update_lecture_embedding(conn, lecture: LectureData) -> int:
    """Upstage 임베딩을 생성해 pgvector 컬럼에 저장한다."""

    # embedding text는 추천 품질을 위해 제목과 설명만 사용한다.
    embedding = embed_text(build_embedding_text(lecture.title, lecture.description))
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE lectures
            SET embedding = %s::vector,
                embedding_updated_at = now(),
                updated_at = now()
            WHERE source_id = %s
            """,
            (_format_pgvector(embedding), lecture.source_id),
        )
        return cur.rowcount


def _lecture_params(lecture: LectureData) -> dict[str, str | None]:
    """LectureData를 SQL named parameter로 전달하기 위한 dict로 변환한다."""

    return {
        "source_id": lecture.source_id,
        "title": lecture.title,
        "description": lecture.description,
        "detail_url": lecture.detail_url,
        "receipt_period": lecture.receipt_period,
        "event_date": lecture.event_date,
        "author": lecture.author,
        "registered_at": lecture.registered_at,
        "content_hash": lecture.content_hash,
    }


def _format_pgvector(embedding: list[float]) -> str:
    """pgvector가 받을 수 있는 '[0.1,0.2,...]' 문자열로 변환한다."""

    # psycopg가 vector 타입을 직접 알지 못하므로 pgvector literal 문자열로 넘긴다.
    return "[" + ",".join(str(value) for value in embedding) + "]"
