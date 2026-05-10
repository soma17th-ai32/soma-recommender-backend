from datetime import datetime

from pydantic import BaseModel, Field


class HistoryInput(BaseModel):
    url: str
    title: str | None = None
    body: str | None = None
    mentor: str | None = None
    taken_at: datetime | None = None


class RecommendationRequest(BaseModel):
    histories: list[HistoryInput]
    limit: int = Field(default=10, ge=1, le=50)


class NormalizedHistory(BaseModel):
    url: str
    title: str | None = None
    body: str | None = None
    mentor: str | None = None
    taken_at: datetime


class RecommendationItem(BaseModel):
    mentoring_id: str
    title: str
    summary: str
    url: str
    mentor: str | None = None
    score: float
    reason: str


class RecommendationResponse(BaseModel):
    request_id: str
    interest_summary: str
    items: list[RecommendationItem]


class AgentRecommendationResult(BaseModel):
    interest_summary: str
    items: list[RecommendationItem]
