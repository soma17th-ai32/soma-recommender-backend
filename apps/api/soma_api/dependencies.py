from soma_api.adapters.agent import (
    Jjjjjk12RecommendationAgentAdapter,
    RecommendationAgentAdapter,
)
from soma_api.services.recommendation_service import RecommendationService
from soma_api.storage.ttl import InMemoryTTLHistoryStore

_history_store = InMemoryTTLHistoryStore()
_agent_adapter: RecommendationAgentAdapter | None = None
_recommendation_service: RecommendationService | None = None


def get_history_store() -> InMemoryTTLHistoryStore:
    return _history_store


def get_agent_adapter() -> RecommendationAgentAdapter:
    global _agent_adapter
    if _agent_adapter is None:
        _agent_adapter = Jjjjjk12RecommendationAgentAdapter()
    return _agent_adapter


def get_recommendation_service() -> RecommendationService:
    global _recommendation_service
    if _recommendation_service is None:
        _recommendation_service = RecommendationService(
            _history_store,
            get_agent_adapter(),
        )
    return _recommendation_service
