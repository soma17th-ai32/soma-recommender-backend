# Lecture Sync DB Test

소마 특강 sync 로직을 로컬 PostgreSQL + pgvector로 테스트하는 절차입니다.

터미널에서 명령이 줄바꿈으로 끊기면 실패할 수 있으니, 아래 명령은 한 줄씩 복사해서 실행합니다.

## 1. Docker 실행 확인

```bash
docker info
```

Docker daemon이 실행 중이 아니라면 Docker Desktop을 먼저 실행합니다.

```bash
open -a Docker
```

## 2. PostgreSQL + pgvector 컨테이너 실행

처음 생성할 때만 실행합니다.

```bash
docker run --name soma-postgres -e POSTGRES_USER=soma -e POSTGRES_PASSWORD=soma -e POSTGRES_DB=soma_recommender -p 5432:5432 -d pgvector/pgvector:pg16
```

이미 컨테이너가 있으면 시작만 합니다.

```bash
docker start soma-postgres
```

## 3. 프로젝트 루트 .env 설정

프로젝트 루트의 `.env_share`를 참고해서 프로젝트 루트에 `.env`를 구성합니다. `.env_share`는 공유용 양식이고, 실제 계정/API key가 들어간 `.env`는 커밋하지 않습니다.

로컬 Docker DB를 사용할 때는 아래 값을 사용합니다.

```env
DATABASE_URL=postgresql://soma:soma@localhost:5432/soma_recommender
```

처음 테스트할 때는 Upstage API 호출 비용과 실행 시간을 줄이기 위해 1페이지만 수집합니다.

```env
SWM_MAX_PAGES=1
```

기존 row의 상세 페이지 재조회 비용을 줄이고 싶으면 선택적으로 interval을 설정합니다. 값은 초 단위 정수입니다. 기본값은 없으며, 비워두면 매 sync마다 기존 row도 상세 페이지를 다시 확인합니다.

예시:

- `3600`: 마지막 확인 후 1시간 안에는 상세 페이지 재조회 생략
- `21600`: 마지막 확인 후 6시간 안에는 상세 페이지 재조회 생략
- `86400`: 마지막 확인 후 1일 안에는 상세 페이지 재조회 생략

```env
SWM_DETAIL_REFRESH_INTERVAL_SECONDS=86400
```

Upstage base URL과 embedding model은 코드에 기본값이 있습니다. 기본값을 쓸 때는 `.env`에 `UPSTAGE_BASE_URL`, `UPSTAGE_EMBEDDING_MODEL`을 넣지 않아도 됩니다.

## 4. DB 스키마 적용

로컬에 `psql`이 없어도 Docker 컨테이너 안의 `psql`로 실행할 수 있습니다.

```bash
docker exec -i soma-postgres psql -U soma -d soma_recommender < apps/api/sql/001_create_lectures.sql
```

테이블 생성 확인:

```bash
docker exec -it soma-postgres psql -U soma -d soma_recommender
```

psql 안에서 실행합니다.

```sql
\dt
```

종료:

```sql
\q
```

## 5. 의존성 동기화

```bash
uv sync --package soma-api
```

## 6. Lecture sync 실행

```bash
.venv/bin/python -m apps.api.lecture_sync --sync
```

이 명령은 소마 로그인, 접수 가능 특강 목록 수집, 상세 페이지 수집, DB insert/update, inactive 처리, Upstage embedding 생성, pgvector 저장을 수행합니다.

## 7. 단위 테스트 실행

```bash
uv run pytest
```

현재 기대 결과:

```text
13 passed
```

## 8. 저장 결과 확인

```bash
docker exec -it soma-postgres psql -U soma -d soma_recommender
```

최근 저장된 특강 확인:

```sql
SELECT source_id, title, status, author, embedding_updated_at, last_seen_at FROM lectures ORDER BY updated_at DESC LIMIT 10;
```

embedding 차원 확인:

```sql
SELECT source_id, vector_dims(embedding) FROM lectures WHERE embedding IS NOT NULL LIMIT 5;
```

종료:

```sql
\q
```

## 9. 자주 나는 문제

Docker daemon이 꺼져 있는 경우:

```text
failed to connect to the docker API
```

해결:

```bash
open -a Docker
```

로컬 `psql`이 없는 경우:

```text
zsh: command not found: psql
```

해결: 로컬 `psql` 대신 `docker exec ... psql` 명령을 사용합니다.

명령이 줄바꿈으로 끊긴 경우:

```text
zsh: no such file or directory
```

해결: 문서의 bash 명령을 한 줄씩 복사해서 실행합니다.
