from datetime import UTC, datetime, timedelta
from threading import RLock

from pydantic import BaseModel

from soma_api.models import NormalizedHistory


class StoredHistoryRequest(BaseModel):
    request_id: str
    histories: list[NormalizedHistory]
    created_at: datetime
    expires_at: datetime


class InMemoryTTLHistoryStore:
    def __init__(self, ttl: timedelta = timedelta(days=7)) -> None:
        self._ttl = ttl
        self._items: dict[str, StoredHistoryRequest] = {}
        self._lock = RLock()

    def save(
        self,
        request_id: str,
        histories: list[NormalizedHistory],
        now: datetime | None = None,
    ) -> StoredHistoryRequest:
        created_at = now or datetime.now(UTC)
        stored = StoredHistoryRequest(
            request_id=request_id,
            histories=histories,
            created_at=created_at,
            expires_at=created_at + self._ttl,
        )
        with self._lock:
            self._items[request_id] = stored
        return stored

    def get(
        self, request_id: str, now: datetime | None = None
    ) -> StoredHistoryRequest | None:
        checked_at = now or datetime.now(UTC)
        with self._lock:
            stored = self._items.get(request_id)
            if stored is None:
                return None
            if stored.expires_at <= checked_at:
                del self._items[request_id]
                return None
            return stored

    def cleanup(self, now: datetime | None = None) -> int:
        checked_at = now or datetime.now(UTC)
        with self._lock:
            expired_request_ids = [
                request_id
                for request_id, stored in self._items.items()
                if stored.expires_at <= checked_at
            ]
            for request_id in expired_request_ids:
                del self._items[request_id]
            return len(expired_request_ids)

    def ready(self) -> bool:
        with self._lock:
            return self._items is not None
