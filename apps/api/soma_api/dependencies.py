from soma_api.adapters.agent import (
    RecommendationAgentAdapter,
    StubRecommendationAgentAdapter,
)
from soma_api.services.recommendation_service import RecommendationService
from soma_api.storage.ttl import InMemoryTTLHistoryStore

_history_store = InMemoryTTLHistoryStore()
_agent_adapter = StubRecommendationAgentAdapter()
_recommendation_service = RecommendationService(_history_store, _agent_adapter)


def get_history_store() -> InMemoryTTLHistoryStore:
    return _history_store


def get_agent_adapter() -> RecommendationAgentAdapter:
    return _agent_adapter


def get_recommendation_service() -> RecommendationService:
    return _recommendation_service
