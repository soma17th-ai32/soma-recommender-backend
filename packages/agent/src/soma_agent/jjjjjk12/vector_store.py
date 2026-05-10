"""jjjjjk12 추천 에이전트의 pgvector 검색 client."""

from __future__ import annotations

from typing import LiteralString

import psycopg
from psycopg.rows import tuple_row

from soma_agent.jjjjjk12.errors import VectorSearchError
from soma_agent.jjjjjk12.schemas import LectureCandidate


class PgvectorLectureSearchClient:
    """lectures 테이블에서 pgvector 유사도 검색을 수행한다."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def search(
        self,
        embedding: list[float],
        limit: int,
        filters: dict | None = None,
    ) -> list[LectureCandidate]:
        """활성 특강 중 query embedding과 가까운 후보를 검색한다."""

        vector = format_pgvector(embedding)
        try:
            return self._search_with_vector(vector, limit)
        except psycopg.Error as error:
            raise VectorSearchError("VectorDB 검색에 실패했습니다.") from error

    def _search_with_vector(
        self,
        vector: str,
        limit: int,
    ) -> list[LectureCandidate]:
        """pgvector literal을 사용해 lectures 테이블을 검색한다."""

        with psycopg.connect(self.database_url, row_factory=tuple_row) as conn:
            with conn.cursor() as cur:
                cur.execute(build_search_sql(), (vector, vector, limit))
                return rows_to_candidates(cur.fetchall())


def build_search_sql() -> LiteralString:
    """활성 특강 embedding 유사도 검색 SQL을 만든다."""

    return """
        SELECT source_id, title, description, detail_url, status,
               1 - (embedding <=> %s::vector) AS score
        FROM lectures
        WHERE status = 'active'
          AND embedding IS NOT NULL
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """


def rows_to_candidates(rows: list[tuple]) -> list[LectureCandidate]:
    """DB row 목록을 추천 후보 목록으로 변환한다."""

    result = []
    for row in rows:
        result.append(row_to_candidate(row))
    return result


def row_to_candidate(row: tuple) -> LectureCandidate:
    """DB row 하나를 추천 후보로 변환한다."""

    return LectureCandidate(
        mentoring_id=row[0],
        title=row[1],
        summary=row[2],
        url=row[3],
        score=float(row[5]),
        is_closed=row[4] != "active",
    )


def format_pgvector(embedding: list[float]) -> str:
    """pgvector가 받을 수 있는 문자열로 변환한다."""

    return "[" + ",".join(str(value) for value in embedding) + "]"
