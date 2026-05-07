"""jjjjjk12 추천 에이전트 설정 로딩."""

from __future__ import annotations

from dataclasses import dataclass
import os

from dotenv import load_dotenv

from soma_agent.jjjjjk12.embedding import DEFAULT_UPSTAGE_BASE_URL
from soma_agent.jjjjjk12.embedding import DEFAULT_UPSTAGE_EMBEDDING_MODEL


DEFAULT_UPSTAGE_CHAT_MODEL = "solar-pro2"


@dataclass(frozen=True)
class Jjjjjk12AgentSettings:
    """jjjjjk12 추천 workflow 생성에 필요한 설정."""

    database_url: str
    upstage_api_key: str
    upstage_base_url: str = DEFAULT_UPSTAGE_BASE_URL
    upstage_embedding_model: str = DEFAULT_UPSTAGE_EMBEDDING_MODEL
    upstage_chat_model: str = DEFAULT_UPSTAGE_CHAT_MODEL
    timeout_seconds: float = 20.0


def load_jjjjjk12_settings() -> Jjjjjk12AgentSettings:
    """환경변수에서 jjjjjk12 Agent 설정을 읽는다."""

    load_dotenv()
    return Jjjjjk12AgentSettings(
        database_url=require_env("DATABASE_URL"),
        upstage_api_key=require_env("UPSTAGE_API_KEY"),
        upstage_base_url=get_env("UPSTAGE_BASE_URL", DEFAULT_UPSTAGE_BASE_URL),
        upstage_embedding_model=get_env("UPSTAGE_EMBEDDING_MODEL", DEFAULT_UPSTAGE_EMBEDDING_MODEL),
        upstage_chat_model=get_env("UPSTAGE_CHAT_MODEL", DEFAULT_UPSTAGE_CHAT_MODEL),
        timeout_seconds=float(get_env("UPSTAGE_TIMEOUT_SECONDS", "20")),
    )


def require_env(name: str) -> str:
    """필수 환경변수를 읽는다."""

    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def get_env(name: str, default: str) -> str:
    """선택 환경변수를 읽는다."""

    return os.getenv(name, default)
