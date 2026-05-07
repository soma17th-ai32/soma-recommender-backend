"""jjjjjk12 추천 에이전트의 workflow 조립."""

from __future__ import annotations

from soma_agent.common.schemas import History
from soma_agent.common.schemas import RecommendationItem
from soma_agent.common.schemas import RecommendationRequest
from soma_agent.common.schemas import RecommendationResult
from soma_agent.jjjjjk12.errors import EmptyHistoryError
from soma_agent.jjjjjk12.errors import NoRecommendationFoundError
from soma_agent.jjjjjk12.schemas import InterestProfile
from soma_agent.jjjjjk12.schemas import LectureCandidate
from soma_agent.jjjjjk12.schemas import ScoredCandidate


class Jjjjjk12RecommendationWorkflow:
    """수강 이력 기반 추천 workflow."""

    def __init__(
        self,
        profile_extractor,
        embedding_client,
        vector_search_client,
        reason_generator,
    ) -> None:
        self.profile_extractor = profile_extractor
        self.embedding_client = embedding_client
        self.vector_search_client = vector_search_client
        self.reason_generator = reason_generator

    def recommend(self, request: RecommendationRequest) -> RecommendationResult:
        """추천 요청을 처리하고 최종 추천 결과를 반환한다."""

        histories = self._prepare_histories(request.histories)
        profile = self.profile_extractor.extract(histories)
        embedding = self._create_query_embedding(profile)
        candidates = self._search_candidates(embedding, request.limit)
        candidates = self._filter_candidates(candidates, histories)
        scored_candidates = self._rank_candidates(candidates, request.limit)
        items = self._build_items(scored_candidates, profile)
        return RecommendationResult(profile.summary, items)

    def _prepare_histories(self, histories: list[History]) -> list[History]:
        """workflow에서 사용할 수강 이력을 준비한다."""

        if not histories:
            raise EmptyHistoryError("사용 가능한 수강 이력이 없습니다.")
        return histories

    def _create_query_embedding(self, profile: InterestProfile) -> list[float]:
        """관심사 프로필을 검색용 임베딩으로 변환한다."""

        query_text = self._build_query_text(profile)
        return self.embedding_client.embed(query_text)

    def _build_query_text(self, profile: InterestProfile) -> str:
        """관심사 프로필을 검색용 문장으로 만든다."""

        lines = [f"관심 요약: {profile.summary}"]
        if profile.keywords:
            lines.append(f"핵심 키워드: {', '.join(profile.keywords)}")
        return "\n".join(lines)

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

        taken_urls = {history.url for history in histories}
        result = []
        for candidate in candidates:
            if candidate.is_closed or candidate.url in taken_urls:
                continue
            result.append(candidate)
        return result

    def _rank_candidates(
        self,
        candidates: list[LectureCandidate],
        limit: int,
    ) -> list[ScoredCandidate]:
        """후보를 점수순으로 정렬하고 Top-K만 남긴다."""

        if not candidates:
            raise NoRecommendationFoundError("추천 가능한 후보가 없습니다.")
        scored_candidates = self._score_candidates(candidates)
        sorted_candidates = sorted(scored_candidates, key=self._score_key, reverse=True)
        return sorted_candidates[:limit]

    def _score_candidates(
        self,
        candidates: list[LectureCandidate],
    ) -> list[ScoredCandidate]:
        """VectorDB 점수를 최종 점수로 사용한다."""

        result = []
        for candidate in candidates:
            result.append(ScoredCandidate(candidate, candidate.score))
        return result

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

    def _score_key(self, scored_candidate: ScoredCandidate) -> float:
        """정렬에 사용할 최종 점수를 반환한다."""

        return scored_candidate.final_score
