from datetime import UTC, datetime, timedelta

from soma_api.models import NormalizedHistory
from soma_api.storage.ttl import InMemoryTTLHistoryStore


def make_history(url: str = "https://example.com/history") -> NormalizedHistory:
    return NormalizedHistory(
        url=url,
        title="FastAPI",
        body=None,
        mentor="Mentor",
        taken_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_save_and_get_returns_stored_request() -> None:
    store = InMemoryTTLHistoryStore(ttl=timedelta(days=7))
    now = datetime(2026, 1, 1, tzinfo=UTC)
    history = make_history()

    stored = store.save("req_1", [history], now)

    assert stored.request_id == "req_1"
    assert store.get("req_1", now) == stored


def test_get_removes_expired_request() -> None:
    store = InMemoryTTLHistoryStore(ttl=timedelta(seconds=1))
    now = datetime(2026, 1, 1, tzinfo=UTC)
    store.save("req_1", [make_history()], now)

    assert store.get("req_1", now + timedelta(seconds=1)) is None
    assert store.get("req_1", now) is None


def test_cleanup_removes_only_expired_requests() -> None:
    store = InMemoryTTLHistoryStore(ttl=timedelta(seconds=10))
    now = datetime(2026, 1, 1, tzinfo=UTC)
    store.save("req_expired", [make_history("https://example.com/old")], now)
    store.save(
        "req_fresh",
        [make_history("https://example.com/new")],
        now + timedelta(seconds=6),
    )

    removed = store.cleanup(now + timedelta(seconds=11))

    assert removed == 1
    assert store.get("req_expired", now + timedelta(seconds=11)) is None
    assert store.get("req_fresh", now + timedelta(seconds=11)) is not None


def test_requests_are_isolated_by_request_id() -> None:
    store = InMemoryTTLHistoryStore()
    now = datetime(2026, 1, 1, tzinfo=UTC)
    first = make_history("https://example.com/first")
    second = make_history("https://example.com/second")

    store.save("req_1", [first], now)
    store.save("req_2", [second], now)

    stored_first = store.get("req_1", now)
    stored_second = store.get("req_2", now)

    assert stored_first is not None
    assert stored_second is not None
    assert stored_first.histories == [first]
    assert stored_second.histories == [second]
