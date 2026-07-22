from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from flipradar.api.schemas.validation import Money, OptionalMoney, PortfolioConditionValue, SetNumber

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
    set_number: SetNumber = Field(..., min_length=1, max_length=32)
    user_goal: UserGoal
    asking_price: OptionalMoney = Field(default=None, ge=0, decimal_places=2)
    condition: PortfolioConditionValue = "unknown"
    shipping_price: Money = Field(default=Decimal("0.00"), ge=0, decimal_places=2)
    marketplace_fee_pct: Decimal = Field(default=Decimal("0.13"), ge=0, le=1)
    target_margin_pct: Decimal = Field(default=Decimal("0.15"), ge=0, le=1)
    purchase_price: OptionalMoney = Field(default=None, ge=0, decimal_places=2)
    quantity: int = Field(default=1, gt=0)
    target_profit_pct: Decimal = Field(default=Decimal("0.25"), ge=0, le=10)


class AnalyzeResponse(BaseModel):
    set_number: str
    user_goal: UserGoal
    asking_price: float | None
    fair_value: float
    score: int
    recommendation: RecommendationDecision
    confidence: ConfidenceBand
    reasoning: str
    market_low: float | None = None
    market_high: float | None = None
    listing_count: int | None = None
    reason_codes: list[str] | None = None
    all_in_price: float | None = None
    discount_pct: float | None = None
    estimated_profit: float | None = None
    estimated_roi_pct: float | None = None
    target_buy_price: float | None = None
    estimated_net_sell_value: float | None = None
    total_estimated_net_value: float | None = None
    cost_basis: float | None = None
    profit: float | None = None
    profit_pct: float | None = None
    trend_pct: float | None = None
    trend_label: str | None = None
    target_sell_price: float | None = None


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
