# Lecture Sync Review Guide

이 문서는 팀원이 소마 특강 sync 기능의 개발 흐름, 구현 범위, 검증 결과를 빠르게 확인하기 위한 리뷰 문서입니다.

## 요약

이번 작업은 소프트웨어 마에스트로 특강 목록을 수집해서 PostgreSQL + pgvector에 저장하는 기능입니다.

현재 구현된 것:

- 소마 사이트 로그인
- 접수 가능 특강 목록 수집
- 특강 상세 페이지 수집
- 제목과 설명만 사용한 Upstage embedding 생성
- PostgreSQL `lectures` 테이블 저장
- pgvector `embedding vector(4096)` 저장
- 현재 목록에 없는 특강 `inactive` 처리
- 다시 목록에 나타난 특강 `active` 처리
- 내용이 바뀐 특강 embedding 재생성
- 로컬 DB 테스트 문서 작성
- 선택적 상세 페이지 재조회 생략 옵션
- 공용 pytest 설정과 단위 테스트 추가
- `lecture_sync` 단일 파일을 역할별 패키지로 분리
- sync 1회당 DB connection 1개 재사용

구현하지 않은 것:

- 추천 로직
- 추천 API 응답 구성
- 운영용 scheduler
- 운영용 logger
- 벡터 검색 index
- migration 도구

## 변경 파일

주요 구현:

- `apps/api/lecture_sync/service.py`
- `apps/api/lecture_sync/crawler.py`
- `apps/api/lecture_sync/parser.py`
- `apps/api/lecture_sync/repository.py`
- `apps/api/lecture_sync/embedding.py`
- `apps/api/lecture_sync/models.py`
- `apps/api/lecture_sync/settings.py`
- `apps/api/lecture_sync/cli.py`

DB 스키마:

- `apps/api/sql/001_create_lectures.sql`

의존성:

- `pyproject.toml`
- `apps/api/pyproject.toml`
- `uv.lock`

테스트:

- `apps/api/tests/unit/test_lecture_sync.py`

테스트 절차 문서:

- `docs/lecture_sync_db_test.md`

AI 참고 문서:

- `docs/lecture_sync_ai_context.md`

## 기능 흐름

전체 실행 명령:

```bash
.venv/bin/python -m apps.api.lecture_sync --sync
```

실행 흐름:

1. `.env_share`를 참고해 구성한 `.env`에서 소마 로그인 정보, Upstage API key, DB URL을 읽습니다.
2. 소마 사이트에 로그인합니다.
3. 접수 가능 특강 목록을 수집합니다.
4. 각 특강의 상세 페이지에 접속해서 제목과 설명을 가져옵니다.
5. DB에 이미 저장된 특강 목록을 조회합니다.
6. DB에는 있는데 현재 목록에 없는 특강은 `inactive`로 바꿉니다.
7. DB에 없는 특강은 insert합니다.
8. 기존에 `inactive`였던 특강이 다시 보이면 `active`로 바꿉니다.
9. `SWM_DETAIL_REFRESH_INTERVAL_SECONDS` 초 안에 이미 확인한 기존 특강은 상세 재조회를 생략할 수 있습니다.
10. 제목 또는 설명이 바뀐 특강은 `content_hash` 변경으로 감지합니다.
11. 신규 또는 변경 특강은 Upstage embedding을 생성해서 pgvector에 저장합니다.
12. 제목이 비어 있는 상세 페이지는 저장하지 않습니다. 설명은 비어 있어도 저장합니다.

## 상태 갱신 규칙

`source_id`

- 소마 HTML의 `qustnrSn` 값입니다.
- DB unique 기준입니다.

`active`

- 현재 접수 가능 목록에서 발견된 특강입니다.

`inactive`

- 이전에는 DB에 있었지만 현재 접수 가능 목록에서는 사라진 특강입니다.

`content_hash`

- `title + description` 기반 SHA-256입니다.
- 값이 바뀌면 embedding을 다시 생성합니다.

`last_seen_at`

- 접수 가능 목록에서 마지막으로 발견된 시각입니다.

`embedding_updated_at`

- embedding을 마지막으로 저장한 시각입니다.

## DB 스키마

테이블: `lectures`

핵심 컬럼:

- `source_id TEXT NOT NULL UNIQUE`
- `title TEXT NOT NULL`
- `description TEXT NOT NULL`
- `detail_url TEXT NOT NULL`
- `status TEXT NOT NULL DEFAULT 'active'`
- `receipt_period TEXT`
- `event_date TEXT`
- `author TEXT`
- `registered_at TEXT`
- `content_hash TEXT NOT NULL`
- `embedding vector(4096)`
- `embedding_updated_at TIMESTAMPTZ`
- `last_seen_at TIMESTAMPTZ`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`

현재 생성 index:

- `status`
- `last_seen_at`

벡터 검색 index는 추천 쿼리 방식이 정해진 뒤 추가하는 것이 좋습니다.

## 로컬 검증 결과

로컬 PostgreSQL + pgvector 컨테이너로 실제 sync를 실행했습니다.

초기 insert 검증 결과:

```text
fetched_count=10
inserted_count=10
updated_count=0
activated_count=0
inactivated_count=0
embedding_pending_count=10
```

리팩터링 후 재실행 결과:

```text
fetched_count=10
inserted_count=0
updated_count=0
activated_count=0
inactivated_count=0
embedding_pending_count=0
```

pgvector 저장 확인:

```sql
SELECT source_id, vector_dims(embedding) FROM lectures WHERE embedding IS NOT NULL LIMIT 5;
```

확인 결과:

```text
vector_dims = 4096
```

즉, 수집, DB insert, Upstage embedding 생성, pgvector 저장까지 정상 동작을 확인했습니다.

단위 테스트:

```text
uv run pytest
13 passed
```

## 리뷰할 때 보면 좋은 지점

`apps/api/lecture_sync/service.py`

- `sync_lecture()`: 전체 orchestration
- `refresh_lecture_status()`: 신규/변경/비활성/재활성 판단
- `should_skip_detail_refresh()`: 선택적 상세 재조회 생략 판단

`apps/api/lecture_sync/crawler.py`

- `fetch_available_lecture_list()`: 목록 페이지 순회
- `fetch_lecture_detail()`: 상세 페이지 추출

`apps/api/lecture_sync/repository.py`

- `insert_lecture()`, `update_lecture()`, `update_lecture_seen()`: DB 저장
- `mark_lectures_inactive()`, `mark_lecture_active()`: 상태 갱신
- `update_lecture_embedding()`: embedding 생성과 pgvector 저장

`apps/api/sql/001_create_lectures.sql`

- pgvector extension 생성
- `lectures` 테이블 생성
- 상태/마지막 발견 시각 index 생성

## 현재 한계

- 현재는 sync 1회당 DB connection 1개를 사용합니다. 운영에서는 connection pool로 확장할 수 있습니다.
- logger는 아직 없습니다. 팀에서 로깅 방식을 정한 뒤 추가할 예정입니다.
- migration 도구는 아직 없습니다. 현재는 SQL 파일을 직접 적용합니다.
- HTML 구조가 바뀌면 selector 수정이 필요합니다.
- embedding 실패 시 재시도/부분 실패 복구 정책은 아직 없습니다.
- `status`는 문자열입니다. 나중에 check constraint 또는 enum으로 제한할 수 있습니다.

## 로컬 테스트 문서

실행 절차는 아래 문서에 정리되어 있습니다.

```text
docs/lecture_sync_db_test.md
```
