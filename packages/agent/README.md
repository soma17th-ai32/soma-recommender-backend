# SOMA Agent

수강 이력 기반 특강 추천 workflow를 제공하는 패키지입니다.

이 패키지는 FastAPI 라우팅이나 요청 검증을 담당하지 않습니다. Backend가 검증한 입력을 받아 관심사 추출, 임베딩, VectorDB 검색, 룰 필터링, 랭킹, 추천 사유 생성을 수행합니다.

## 현재 구현된 Agent

현재 구현된 agent 이름은 `jjjjjk12`입니다.

```text
packages/agent/src/soma_agent/
  common/
    interfaces.py
    schemas.py

  jjjjjk12/
    factory.py
    workflow.py
    history_preprocessor.py
    profile_extractor.py
    embedding.py
    vector_store.py
    rules.py
    ranker.py
    reason_generator.py
    prompts.py
    settings.py
```

## 입력

Backend는 공통 입력 스키마인 `RecommendationRequest`를 agent에 전달합니다.

```python
RecommendationRequest(
    histories=[
        History(
            title="FastAPI로 백엔드 API 만들기",
            body="FastAPI, 인증, DB 연동, 배포를 다루는 멘토링입니다.",
            url="https://example.com/mentorings/123",
            mentor="홍길동",
            taken_at="2026-05-01T10:00:00+09:00",
        )
    ],
    limit=10,
)
```

`mentor`는 입력에 남아 있지만, 현재 `jjjjjk12` 추천 로직과 추천 근거에는 사용하지 않습니다.

## 출력

Agent는 공통 출력 스키마인 `RecommendationResult`를 반환합니다.

```python
RecommendationResult(
    interest_summary="백엔드 API 개발과 실무형 프로젝트 구현에 관심이 높습니다.",
    items=[
        RecommendationItem(
            mentoring_id="10268",
            title="실전 FastAPI 백엔드 설계",
            summary="FastAPI 기반 API 구조와 인증, DB 연동을 다룹니다.",
            url="https://example.com/mentorings/456",
            score=0.91,
            reason="FastAPI와 백엔드 API 관심사에 맞는 실무형 특강입니다.",
        )
    ],
)
```

## jjjjjk12 Workflow

처리 순서는 다음과 같습니다.

1. 수강 이력을 전처리합니다.
2. LLM으로 관심사 요약과 키워드를 추출합니다.
3. 관심사 요약과 키워드로 검색 query text를 만듭니다.
4. Upstage embedding API로 query embedding을 생성합니다.
5. `lectures` 테이블의 pgvector embedding과 유사도 검색을 수행합니다.
6. 마감된 후보와 이미 수강한 후보를 제외합니다.
7. 최종 점수 기준으로 Top-K를 반환합니다.
8. LLM으로 추천 사유를 생성합니다.

## 수강 이력 전처리

수강 이력은 LLM에 그대로 전부 전달하지 않습니다.

- `url`이 없는 이력은 제외합니다.
- `title`과 `body`가 둘 다 없는 이력은 제외합니다.
- 같은 요청 안에서 `url`이 같은 이력은 중복 제거합니다.
- `taken_at` 기준으로 최신순 정렬합니다.
- 관심사 추출에는 최신 N개만 사용합니다.

기본 N은 `10`입니다.

## LLM에 전달하는 정보

관심사 추출 시 LLM에 전달하는 정보는 다음뿐입니다.

- 수강 이력 `title`
- 수강 이력 `body`

관심사 추출 시 LLM에 전달하지 않는 정보는 다음과 같습니다.

- `url`
- `mentor`
- `taken_at`
- 사용자 식별자

추천 사유 생성 시 LLM에 전달하는 정보는 다음입니다.

- 관심사 요약
- 관심 키워드
- 추천 후보 제목
- 추천 후보 요약
- 최종 추천 점수

## 환경변수

`create_jjjjjk12_workflow()`를 사용하려면 다음 환경변수가 필요합니다.

| 이름 | 필수 | 기본값 | 설명 |
| --- | --- | --- | --- |
| `DATABASE_URL` | Y | 없음 | PostgreSQL/pgvector 연결 문자열 |
| `UPSTAGE_API_KEY` | Y | 없음 | Upstage API key |
| `UPSTAGE_BASE_URL` | N | `https://api.upstage.ai/v1/solar` | Upstage OpenAI-compatible base URL |
| `UPSTAGE_EMBEDDING_MODEL` | N | `solar-embedding-1-large-query` | 검색 query embedding 모델 |
| `UPSTAGE_CHAT_MODEL` | N | `solar-pro2` | 관심사 추출과 추천 사유 생성 모델 |
| `UPSTAGE_TIMEOUT_SECONDS` | N | `20` | Upstage 요청 timeout |
| `JJJJJK12_PROFILE_HISTORY_LIMIT` | N | `10` | 관심사 추출에 사용할 최신 수강 이력 개수 |
| `JJJJJK12_PROFILE_TITLE_MAX_CHARS` | N | `120` | LLM에 보낼 title 최대 길이 |
| `JJJJJK12_PROFILE_BODY_MAX_CHARS` | N | `800` | LLM에 보낼 body 최대 길이 |

## DB 전제

검색 대상은 `lectures` 테이블입니다.

필요한 주요 컬럼은 다음과 같습니다.

- `source_id`
- `title`
- `description`
- `detail_url`
- `status`
- `embedding`

현재 embedding 컬럼은 `vector(4096)`을 전제로 합니다. `solar-embedding-1-large-query`의 embedding 차원도 `4096`입니다.

## 사용 예시

```python
from soma_agent.common.schemas import History
from soma_agent.common.schemas import RecommendationRequest
from soma_agent.jjjjjk12.factory import create_jjjjjk12_workflow


workflow = create_jjjjjk12_workflow()

request = RecommendationRequest(
    histories=[
        History(
            title="FastAPI로 백엔드 API 만들기",
            body="FastAPI, 인증, DB 연동, 배포를 다루는 멘토링입니다.",
            url="https://example.com/mentorings/123",
            taken_at="2026-05-01T10:00:00+09:00",
        )
    ],
    limit=10,
)

result = workflow.recommend(request)
```

## 예외

`jjjjjk12` workflow에서 발생할 수 있는 주요 예외는 다음과 같습니다.

| 예외 | 의미 |
| --- | --- |
| `EmptyHistoryError` | 추천에 사용할 수강 이력이 없음 |
| `ProfileExtractionError` | LLM 관심사 추출 실패 |
| `ReasonGenerationError` | LLM 추천 사유 생성 실패 |
| `EmbeddingProviderError` | Upstage embedding 생성 실패 |
| `VectorSearchError` | pgvector 검색 실패 |
| `NoRecommendationFoundError` | 필터링 후 추천 가능한 후보가 없음 |

관심사 추출과 추천 사유 생성은 LLM 실패 시 fallback 로직을 사용합니다.

## 현재 남은 통합 작업

- `apps/api/main.py`에 `POST /v1/recommendations` endpoint 구현
- API request schema validation 구현
- API 응답에 `request_id` 추가
- Agent 예외를 공통 HTTP error response로 변환
- TTL storage 저장 흐름 연결
- 실제 `DATABASE_URL` 환경에서 pgvector 검색 포함 end-to-end 확인
