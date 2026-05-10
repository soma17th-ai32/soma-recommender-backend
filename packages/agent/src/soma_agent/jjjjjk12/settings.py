"""jjjjjk12 추천 에이전트 설정 로딩."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from soma_agent.jjjjjk12.embedding import (
    DEFAULT_UPSTAGE_BASE_URL,
    DEFAULT_UPSTAGE_EMBEDDING_MODEL,
)

DEFAULT_UPSTAGE_CHAT_MODEL = "solar-pro2"
DEFAULT_PROFILE_HISTORY_LIMIT = 10
DEFAULT_PROFILE_TITLE_MAX_CHARS = 120
DEFAULT_PROFILE_BODY_MAX_CHARS = 800


@dataclass(frozen=True)
class Jjjjjk12AgentSettings:
    """jjjjjk12 추천 workflow 생성에 필요한 설정."""

    database_url: str
    upstage_api_key: str
    upstage_base_url: str = DEFAULT_UPSTAGE_BASE_URL
    upstage_embedding_model: str = DEFAULT_UPSTAGE_EMBEDDING_MODEL
    upstage_chat_model: str = DEFAULT_UPSTAGE_CHAT_MODEL
    timeout_seconds: float = 20.0
    profile_history_limit: int = DEFAULT_PROFILE_HISTORY_LIMIT
    profile_title_max_chars: int = DEFAULT_PROFILE_TITLE_MAX_CHARS
    profile_body_max_chars: int = DEFAULT_PROFILE_BODY_MAX_CHARS


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
        profile_history_limit=get_int_env(
            "JJJJJK12_PROFILE_HISTORY_LIMIT",
            DEFAULT_PROFILE_HISTORY_LIMIT,
        ),
        profile_title_max_chars=get_int_env(
            "JJJJJK12_PROFILE_TITLE_MAX_CHARS",
            DEFAULT_PROFILE_TITLE_MAX_CHARS,
        ),
        profile_body_max_chars=get_int_env(
            "JJJJJK12_PROFILE_BODY_MAX_CHARS",
            DEFAULT_PROFILE_BODY_MAX_CHARS,
        ),
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


def get_int_env(name: str, default: int) -> int:
    """정수형 선택 환경변수를 읽는다."""

    value = os.getenv(name)
    if not value:
        return default
    return int(value)
