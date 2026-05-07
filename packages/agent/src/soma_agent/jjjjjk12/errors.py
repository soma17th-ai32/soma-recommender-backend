"""jjjjjk12 추천 에이전트 전용 예외."""

from soma_agent.common.errors import SomaAgentError


class Jjjjjk12AgentError(SomaAgentError):
    """jjjjjk12 추천 에이전트의 기본 예외."""


class EmptyHistoryError(Jjjjjk12AgentError):
    """사용 가능한 수강 이력이 없을 때 발생한다."""


class ProfileExtractionError(Jjjjjk12AgentError):
    """관심사 프로필 추출에 실패했을 때 발생한다."""


class ReasonGenerationError(Jjjjjk12AgentError):
    """추천 사유 생성에 실패했을 때 발생한다."""


class EmbeddingProviderError(Jjjjjk12AgentError):
    """임베딩 생성에 실패했을 때 발생한다."""


class VectorSearchError(Jjjjjk12AgentError):
    """VectorDB 검색에 실패했을 때 발생한다."""


class NoRecommendationFoundError(Jjjjjk12AgentError):
    """추천 가능한 후보가 없을 때 발생한다."""
