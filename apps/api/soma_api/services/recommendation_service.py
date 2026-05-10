from datetime import UTC, datetime

from lecture_sync.service import sync_lecture
from soma_api.adapters.agent import RecommendationAgentAdapter
from soma_api.errors import ApiError
from soma_api.models import (
    HistoryInput,
    NormalizedHistory,
    RecommendationRequest,
    RecommendationResponse,
)
from soma_api.storage.ttl import InMemoryTTLHistoryStore

EMPTY_HISTORY = "EMPTY_HISTORY"
INVALID_HISTORY_PAYLOAD = "INVALID_HISTORY_PAYLOAD"
NO_RECOMMENDATION_FOUND = "NO_RECOMMENDATION_FOUND"


class RecommendationService:
    def __init__(
        self,
        history_store: InMemoryTTLHistoryStore,
        agent_adapter: RecommendationAgentAdapter,
    ) -> None:
        self._history_store = history_store
        self._agent_adapter = agent_adapter

    def recommend(
        self,
        request: RecommendationRequest,
        request_id: str,
        received_at: datetime | None = None,
    ) -> RecommendationResponse:
        sync_lecture()
        now = received_at or datetime.now(UTC)
        histories = self._normalize_histories(request.histories, now)
        self._history_store.cleanup(now)
        self._history_store.save(request_id, histories, now)

        result = self._agent_adapter.recommend(histories, request.limit, request_id)
        if not result.items:
            raise ApiError(
                NO_RECOMMENDATION_FOUND,
                "No recommendation candidates were found",
                400,
            )

        return RecommendationResponse(
            request_id=request_id,
            interest_summary=result.interest_summary,
            items=result.items,
        )

    def _normalize_histories(
        self, histories: list[HistoryInput], received_at: datetime
    ) -> list[NormalizedHistory]:
        if not histories:
            raise ApiError(EMPTY_HISTORY, "histories must not be empty", 400)

        normalized: list[NormalizedHistory] = []
        seen_urls: set[str] = set()

        for index, history in enumerate(histories):
            title = self._trim_or_none(history.title)
            body = self._trim_or_none(history.body)
            mentor = self._trim_or_none(history.mentor)
            url = history.url.strip()

            if not url:
                raise ApiError(
                    INVALID_HISTORY_PAYLOAD,
                    f"histories[{index}].url must not be empty",
                    400,
                )

            if not title and not body:
                raise ApiError(
                    INVALID_HISTORY_PAYLOAD,
                    f"histories[{index}].title or histories[{index}].body is required",
                    400,
                )

            if url in seen_urls:
                continue
            seen_urls.add(url)

            normalized.append(
                NormalizedHistory(
                    url=url,
                    title=title,
                    body=body,
                    mentor=mentor,
                    taken_at=history.taken_at or received_at,
                )
            )

        if not normalized:
            raise ApiError(EMPTY_HISTORY, "histories must not be empty", 400)

        return normalized

    @staticmethod
    def _trim_or_none(value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None
