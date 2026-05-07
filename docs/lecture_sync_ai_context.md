# Lecture Sync AI Context

이 문서는 팀원의 AI 에이전트가 소마 특강 수집/저장 구현을 빠르게 이해하고 이어서 작업할 수 있도록 만든 참고 문서입니다.

## 작업 범위

현재 구현은 `apps/api/lecture_sync` 패키지에 있습니다.

주요 파일:

- `apps/api/lecture_sync/service.py`: sync orchestration과 상태 갱신 흐름
- `apps/api/lecture_sync/crawler.py`: 소마 로그인, 세션 확인, 목록/상세 수집
- `apps/api/lecture_sync/parser.py`: 목록 HTML 파싱, URL/query helper, content hash
- `apps/api/lecture_sync/repository.py`: PostgreSQL/pgvector 저장
- `apps/api/lecture_sync/embedding.py`: Upstage embedding 호출
- `apps/api/lecture_sync/models.py`: dataclass 모델
- `apps/api/lecture_sync/settings.py`: `.env` 기반 설정 로드
- `apps/api/lecture_sync/cli.py`: 로컬 CLI 출력
- `apps/api/sql/001_create_lectures.sql`: `lectures` 테이블과 pgvector extension 생성 SQL
- `apps/api/pyproject.toml`: API 패키지 의존성
- `apps/api/tests/unit/test_lecture_sync.py`: 순수 helper와 fast-path 단위 테스트
- `docs/lecture_sync_db_test.md`: 로컬 DB 테스트 절차

이 구현은 추천 로직을 담당하지 않습니다. 추천 API나 agent 패키지의 추천 알고리즘은 다른 담당 영역입니다.

## lecture_sync 책임

`lecture_sync` 패키지의 책임:

- 소마 사이트 로그인
- 로그인 세션 유지 확인
- 접수 가능 특강 목록 수집
- 상세 페이지에서 제목/설명 수집
- `title + description` 기반 `content_hash` 생성
- 신규 특강 insert
- 기존 특강 변경 감지
- 목록에서 사라진 특강 `inactive` 처리
- 다시 나타난 특강 `active` 처리
- Upstage embedding 생성
- `lectures.embedding` pgvector 컬럼 갱신

## 실행 진입점

로컬 미리보기:

```bash
.venv/bin/python -m apps.api.lecture_sync
```

첫 번째 특강 embedding 확인:

```bash
.venv/bin/python -m apps.api.lecture_sync --embed
```

DB sync 실행:

```bash
.venv/bin/python -m apps.api.lecture_sync --sync
```

## 환경변수

프로젝트 루트 `.env`에서 읽습니다. 팀원은 프로젝트 루트의 `.env_share`를 참고해서 각자 `.env`를 구성하면 됩니다. 실제 값이 들어간 `.env`는 문서나 코드에 커밋하지 않습니다.

필수:

- `SWM_BASE_URL`
- `SWM_LOGIN_URL`
- `SWM_NOTICE_LIST_URL`
- `SWM_USERNAME`
- `SWM_PASSWORD`
- `UPSTAGE_API_KEY`
- `DATABASE_URL`

선택:

- `SWM_MAX_PAGES`: 수집할 최대 페이지 수. 로컬 테스트에서는 `1` 권장
- `SWM_DETAIL_REFRESH_INTERVAL_SECONDS`: 기존 row의 상세 페이지 재조회 생략 interval. 초 단위 정수 사용. 예: `3600`은 1시간, `86400`은 1일. 빈 값이면 매 sync마다 기존 row도 상세 페이지를 다시 확인
- `SWM_TIMEOUT_SECONDS`: 요청 timeout. 기본값 `20`
- `USER_AGENT`: 요청 User-Agent override
- `UPSTAGE_BASE_URL`: 코드 기본값 `https://api.upstage.ai/v1`. 기본값을 쓸 때는 `.env`에 없어도 됨
- `UPSTAGE_EMBEDDING_MODEL`: 코드 기본값 `embedding-passage`. 기본값을 쓸 때는 `.env`에 없어도 됨

## 데이터 모델

`LectureListItem`

- 목록 페이지에서 읽은 최소 정보
- `source_id`, `title`, `detail_url`, `status`, `receipt_period`, `event_date`, `author`, `registered_at`

`LectureDetail`

- 상세 페이지에서 읽은 embedding 대상 정보
- `source_id`, `title`, `description`, `detail_url`, `content_hash`
- `title`이 비어 있으면 저장/임베딩 전에 `RuntimeError`
- `description`은 SOMA 실제 데이터에서 비어 있을 수 있어 빈 문자열도 허용

`LectureData`

- 목록 메타데이터와 상세 본문을 합친 DB 저장 단위
- insert/update/embedding 저장 함수가 이 타입을 받음

`LectureRecord`

- DB에 이미 존재하는 row의 비교용 정보
- `source_id`, `title`, `description`, `status`, `content_hash`, `last_seen_at`

`SyncLectureResult`

- 한 번의 sync 결과 count
- `fetched_count`, `inserted_count`, `updated_count`, `activated_count`, `inactivated_count`, `embedding_pending_count`

## Sync Flow

`sync_lecture()` 흐름:

1. `load_soma_settings()`로 소마 접속 설정을 읽음
2. `create_soma_session()`으로 `requests.Session` 생성
3. `is_session_alive()`가 false이면 `login_soma_site()` 실행
4. `fetch_available_lecture_list()`로 현재 접수 가능 특강 목록 수집
5. `refresh_lecture_status()`로 DB 상태와 embedding 갱신

`refresh_lecture_status()` 흐름:

1. `get_existing_lectures()`로 DB 기존 row 조회
2. 현재 수집 목록에 없는 기존 row는 `mark_lectures_inactive()`로 `inactive`
3. 신규 row는 `fetch_lecture_data()` 후 `insert_lecture()`
4. 신규 row는 `update_lecture_embedding()`으로 embedding 생성/저장
5. 기존 row가 `inactive`였다가 다시 보이면 `mark_lecture_active()`
6. `SWM_DETAIL_REFRESH_INTERVAL_SECONDS` 안에 이미 확인한 기존 row는 상세 재조회를 생략하고 목록 메타데이터만 갱신
7. 기존 row의 `content_hash`가 바뀌면 `update_lecture()` 후 embedding 재생성
8. 기존 row의 본문이 그대로면 `update_lecture_seen()`으로 목록 메타데이터와 `last_seen_at`만 갱신

## DB Schema

스키마 파일은 `apps/api/sql/001_create_lectures.sql`입니다.

중요 컬럼:

- `source_id`: 소마 HTML의 `qustnrSn`, unique 기준
- `title`: 특강 제목, embedding 대상
- `description`: 상세 설명, embedding 대상
- `status`: `active` 또는 `inactive`
- `content_hash`: `title + description` 기반 SHA-256
- `embedding`: `vector(4096)`, Upstage embedding 저장
- `embedding_updated_at`: embedding 저장 시각
- `last_seen_at`: 접수 가능 목록에서 마지막으로 발견된 시각

현재 index:

- `lectures_status_idx`
- `lectures_last_seen_at_idx`

벡터 검색용 index는 아직 없습니다. 추천 쿼리 패턴이 정해진 뒤 별도 migration으로 추가하는 것이 적절합니다.

## 구현상 주의점

- 크롤링 HTML selector는 소마 페이지 구조에 의존합니다.
- 소마 로그인은 `form#login_form`과 `/sw/member/user/checkStat.json` 호출에 의존합니다.
- 상세 설명은 `.bbs-view-new > .cont`, `.bbs-view-new .cont`에서 추출합니다.
- 상세 제목이 비면 DB 저장과 embedding 생성을 중단합니다. 설명은 비어 있어도 저장합니다.
- embedding은 제목과 설명만 사용합니다. 작성자, 일시, 접수 기간은 embedding 대상이 아닙니다.
- `content_hash`가 바뀐 경우 기존 embedding을 `NULL`로 비운 뒤 재생성합니다.
- `sync_lecture()`는 한 번 연 DB connection을 repository 함수들에 전달합니다.
- `SWM_DETAIL_REFRESH_INTERVAL_SECONDS`를 설정하면 최근에 확인한 기존 row는 상세 페이지 재조회와 embedding 재확인을 생략합니다.
- 현재 로거는 의도적으로 넣지 않았습니다.

## 검증 상태

- `uv run pytest`: 13 passed
- `.venv/bin/python -m apps.api.lecture_sync --help`: OK
- `.venv/bin/python -m apps.api.lecture_sync --sync`: 리팩터링 후 실행 성공
- pgvector 확인: `vector_dims(embedding) = 4096`

## 다음 작업 후보

- DB connection pool 도입
- migration 도구 도입 여부 결정
- 벡터 검색 index 추가
- sync를 FastAPI route, scheduler, admin command 중 어디서 실행할지 결정
- 수집 실패/embedding 실패 시 재시도 정책 추가
- 상태값을 문자열 대신 enum 또는 check constraint로 제한
