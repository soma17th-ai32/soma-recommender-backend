"""jjjjjk12 추천 에이전트의 workflow 조립."""

from __future__ import annotations

from soma_agent.common.schemas import (
    History,
    RecommendationItem,
    RecommendationRequest,
    RecommendationResult,
)
from soma_agent.jjjjjk12.history_preprocessor import prepare_histories
from soma_agent.jjjjjk12.query_builder import build_query_text
from soma_agent.jjjjjk12.ranker import rank_candidates
from soma_agent.jjjjjk12.rules import filter_recommendable_candidates
from soma_agent.jjjjjk12.schemas import InterestProfile, LectureCandidate, ScoredCandidate


class Jjjjjk12RecommendationWorkflow:
    """수강 이력 기반 추천 workflow."""

    def __init__(
        self,
        profile_extractor,
        embedding_client,
        vector_search_client,
        reason_generator,
        profile_history_limit: int = 10,
    ) -> None:
        self.profile_extractor = profile_extractor
        self.embedding_client = embedding_client
        self.vector_search_client = vector_search_client
        self.reason_generator = reason_generator
        self.profile_history_limit = profile_history_limit

    def recommend(self, request: RecommendationRequest) -> RecommendationResult:
        """추천 요청을 처리하고 최종 추천 결과를 반환한다."""

        histories = self._prepare_histories(request.histories)
        profile_histories = self._select_profile_histories(histories)
        profile = self.profile_extractor.extract(profile_histories)
        embedding = self._create_query_embedding(profile)
        candidates = self._search_candidates(embedding, request.limit)
        candidates = self._filter_candidates(candidates, histories)
        scored_candidates = self._rank_candidates(candidates, request.limit)
        items = self._build_items(scored_candidates, profile)
        return RecommendationResult(profile.summary, items)

    def _prepare_histories(self, histories: list[History]) -> list[History]:
        """workflow에서 사용할 수강 이력을 준비한다."""

        return prepare_histories(histories)

    def _select_profile_histories(self, histories: list[History]) -> list[History]:
        """관심사 추출에 사용할 최신 수강 이력만 고른다."""

        limit = max(self.profile_history_limit, 1)
        return histories[:limit]

    def _create_query_embedding(self, profile: InterestProfile) -> list[float]:
        """관심사 프로필을 검색용 임베딩으로 변환한다."""

        query_text = build_query_text(profile)
        return self.embedding_client.embed(query_text)

    def _search_candidates(
        self,
        embedding: list[float],
        limit: int,
    ) -> list[LectureCandidate]:
        """VectorDB에서 추천 후보를 넉넉히 검색한다."""

        candidate_limit = max(limit * 3, 20)
        filters = {"is_closed": False}
        return self.vector_search_client.search(embedding, candidate_limit, filters)

    def _filter_candidates(
        self,
        candidates: list[LectureCandidate],
        histories: list[History],
    ) -> list[LectureCandidate]:
        """마감 후보와 이미 수강한 후보를 제외한다."""

        return filter_recommendable_candidates(candidates, histories)

    def _rank_candidates(
        self,
        candidates: list[LectureCandidate],
        limit: int,
    ) -> list[ScoredCandidate]:
        """후보를 점수순으로 정렬하고 Top-K만 남긴다."""

        return rank_candidates(candidates, limit)

    def _build_items(
        self,
        scored_candidates: list[ScoredCandidate],
        profile: InterestProfile,
    ) -> list[RecommendationItem]:
        """점수화된 후보를 응답 항목으로 변환한다."""

        result = []
        for scored_candidate in scored_candidates:
            item = self._build_item(scored_candidate, profile)
            result.append(item)
        return result

    def _build_item(
        self,
        scored_candidate: ScoredCandidate,
        profile: InterestProfile,
    ) -> RecommendationItem:
        """추천 후보 하나를 최종 응답 항목으로 변환한다."""

        candidate = scored_candidate.candidate
        reason = self.reason_generator.generate(scored_candidate, profile)
        return RecommendationItem(
            candidate.mentoring_id,
            candidate.title,
            candidate.summary,
            candidate.url,
            scored_candidate.final_score,
            reason,
        )
