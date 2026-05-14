"""jjjjjk12 추천 에이전트의 workflow 조립."""

from __future__ import annotations

import logging
from time import perf_counter

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

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


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

        started_at = perf_counter()
        logger.info(
            "[AGENT 1/8] 추천 Agent workflow 시작 | histories=%s | limit=%s",
            len(request.histories),
            request.limit,
        )
        logger.info("[AGENT 2/8] 수강 이력 전처리 중...")
        histories = self._prepare_histories(request.histories)
        logger.info(
            "[AGENT 2/8] 수강 이력 전처리 완료 | prepared_histories=%s",
            len(histories),
        )
        profile_histories = self._select_profile_histories(histories)
        logger.info(
            "[AGENT 3/8] 관심사 추출 대상 이력 선택 완료 | selected_histories=%s | limit=%s",
            len(profile_histories),
            self.profile_history_limit,
        )
        logger.info("[AGENT 4/8] 관심사 프로필 추출 중...")
        profile = self.profile_extractor.extract(profile_histories)
        logger.info(
            "[AGENT 4/8] 관심사 프로필 추출 완료 | keywords=%s | summary=%s",
            len(profile.keywords),
            _preview_text(profile.summary),
        )
        logger.info("[AGENT 5/8] 검색용 임베딩 생성 중...")
        embedding = self._create_query_embedding(profile)
        logger.info(
            "[AGENT 5/8] 검색용 임베딩 생성 완료 | dimensions=%s",
            len(embedding),
        )
        logger.info("[AGENT 6/8] VectorDB 후보 검색 중...")
        candidates = self._search_candidates(embedding, request.limit)
        logger.info(
            "[AGENT 6/8] VectorDB 후보 검색 완료 | candidates=%s",
            len(candidates),
        )
        before_filter_count = len(candidates)
        candidates = self._filter_candidates(candidates, histories)
        logger.info(
            "[AGENT 7/8] 추천 후보 필터링 완료 | before=%s | after=%s",
            before_filter_count,
            len(candidates),
        )
        scored_candidates = self._rank_candidates(candidates, request.limit)
        logger.info(
            "[AGENT 7/8] 추천 후보 랭킹 완료 | ranked=%s",
            len(scored_candidates),
        )
        logger.info("[AGENT 8/8] 추천 사유 생성 및 응답 변환 중...")
        items = self._build_items(scored_candidates, profile)
        logger.info(
            "[AGENT 8/8] 추천 사유 생성 및 응답 변환 완료 | items=%s",
            len(items),
        )
        elapsed_seconds = perf_counter() - started_at
        logger.info(
            "[AGENT DONE] 추천 Agent workflow 완료 | items=%s | elapsed=%.2fs",
            len(items),
            elapsed_seconds,
        )
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


def _preview_text(value: str, max_chars: int = 40) -> str:
    """데모 로그가 너무 길어지지 않도록 한 줄 요약만 보여준다."""

    text = " ".join(value.split())
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}..."
