from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request

from soma_api.dependencies import get_recommendation_service
from soma_api.models import RecommendationRequest, RecommendationResponse
from soma_api.services.recommendation_service import RecommendationService

router = APIRouter(prefix="/v1", tags=["recommendations"])


@router.post("/recommendations", response_model=RecommendationResponse)
async def create_recommendations(
    payload: RecommendationRequest,
    request: Request,
    service: RecommendationService = Depends(get_recommendation_service),
) -> RecommendationResponse:
    return service.recommend(
        payload,
        request.state.request_id,
        datetime.now(UTC),
    )
