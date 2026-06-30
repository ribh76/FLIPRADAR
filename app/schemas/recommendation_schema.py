from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserGoal(StrEnum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    HOLD_OR_SELL = "hold_or_sell"
    BUY_SET = "buy_set"
    SELL_SET = "sell_set"
    HOLD_VS_SELL = "hold_vs_sell"
    BUY_VS_PASS = "buy_vs_pass"


class RecommendationDecision(StrEnum):
    BUY = "BUY"
    PASS = "PASS"
    SELL = "SELL"
    HOLD = "HOLD"
    WATCH = "WATCH"


class ConfidenceBand(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AnalyzeRequest(BaseModel):
    set_number: str = Field(..., min_length=1)
    user_goal: UserGoal
    asking_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)

    @field_validator("set_number", mode="before")
    @classmethod
    def normalize_set_number(cls, value: object) -> str:
        return str(value).strip()


class AnalyzeResponse(BaseModel):
    set_number: str
    user_goal: UserGoal
    asking_price: float | None
    fair_value: float
    score: int
    recommendation: RecommendationDecision
    confidence: ConfidenceBand
    reasoning: str


class RecommendationResponse(BaseModel):
    id: UUID
    lego_set_id: UUID
    set_number: str
    user_goal: UserGoal
    recommendation: RecommendationDecision
    fair_value: int
    confidence: ConfidenceBand
    confidence_score: Decimal
    asking_price: Decimal | None
    reason: str
    market_summary: dict | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
