"""lecture sync 실행에 필요한 환경변수를 dataclass 설정으로 변환한다."""

import os

from dotenv import load_dotenv

from lecture_sync.models import SomaSettings, UpstageSettings


def load_soma_settings() -> SomaSettings:
    """프로젝트 루트 .env와 환경변수에서 소마 사이트 접속 설정을 읽는다."""

    load_dotenv()

    max_pages = os.getenv("SWM_MAX_PAGES")
    timeout_seconds = os.getenv("SWM_TIMEOUT_SECONDS", "20")
    detail_refresh_interval_seconds = os.getenv("SWM_DETAIL_REFRESH_INTERVAL_SECONDS")

    # 로그인과 목록 수집에 없으면 실행할 수 없는 값만 필수로 검증한다.
    required_values = {
        "SWM_BASE_URL": os.getenv("SWM_BASE_URL"),
        "SWM_LOGIN_URL": os.getenv("SWM_LOGIN_URL"),
        "SWM_NOTICE_LIST_URL": os.getenv("SWM_NOTICE_LIST_URL"),
        "SWM_USERNAME": os.getenv("SWM_USERNAME"),
        "SWM_PASSWORD": os.getenv("SWM_PASSWORD"),
    }
    missing = [name for name, value in required_values.items() if not value]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    return SomaSettings(
        base_url=required_values["SWM_BASE_URL"] or "",
        login_url=required_values["SWM_LOGIN_URL"] or "",
        lecture_list_url=required_values["SWM_NOTICE_LIST_URL"] or "",
        username=required_values["SWM_USERNAME"] or "",
        password=required_values["SWM_PASSWORD"] or "",
        timeout_seconds=float(timeout_seconds),
        user_agent=os.getenv("USER_AGENT", "Mozilla/5.0 (compatible; SOMA-Recommender/0.1)"),
        # 빈 값이면 제한 없이 모든 페이지/모든 상세 페이지를 확인한다.
        max_pages=int(max_pages) if max_pages else None,
        detail_refresh_interval_seconds=(
            int(detail_refresh_interval_seconds) if detail_refresh_interval_seconds else None
        ),
    )


def load_upstage_settings() -> UpstageSettings:
    """프로젝트 루트 .env와 환경변수에서 Upstage 임베딩 설정을 읽는다."""

    load_dotenv()

    api_key = os.getenv("UPSTAGE_API_KEY")
    if not api_key:
        raise RuntimeError("Missing required environment variable: UPSTAGE_API_KEY")

    return UpstageSettings(
        api_key=api_key,
        base_url=os.getenv("UPSTAGE_BASE_URL", "https://api.upstage.ai/v1"),
        embedding_model=os.getenv("UPSTAGE_EMBEDDING_MODEL", "embedding-passage"),
    )


def load_database_url() -> str:
    """프로젝트 루트 .env와 환경변수에서 PostgreSQL 연결 문자열을 읽는다."""

    load_dotenv()

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("Missing required environment variable: DATABASE_URL")
    return database_url
