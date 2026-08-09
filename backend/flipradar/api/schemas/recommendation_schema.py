from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from flipradar.api.schemas.validation import (
    Money,
    OptionalMoney,
    PortfolioConditionValue,
    SetNumber,
)
from flipradar.domain.models.enums import PortfolioCondition, RecommendationDecision


class UserGoal(StrEnum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    HOLD_OR_SELL = "hold_or_sell"
    BUY_SET = "buy_set"
    SELL_SET = "sell_set"
    HOLD_VS_SELL = "hold_vs_sell"
    BUY_VS_PASS = "buy_vs_pass"


class ConfidenceBand(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ManualValuationOverride(BaseModel):
    """A user-validated valuation used when market evidence is unavailable."""

    expected_value: Money = Field(..., gt=0, decimal_places=2)
    low_value: OptionalMoney = Field(default=None, gt=0, decimal_places=2)
    high_value: OptionalMoney = Field(default=None, gt=0, decimal_places=2)
    reason: str = Field(..., min_length=3, max_length=500)

    @model_validator(mode="after")
    def validate_range(self) -> ManualValuationOverride:
        low = self.low_value if self.low_value is not None else self.expected_value
        high = self.high_value if self.high_value is not None else self.expected_value
        if low > self.expected_value or self.expected_value > high:
            raise ValueError(
                "manual valuation must satisfy low_value <= expected_value <= high_value"
            )
        return self


class AnalyzeRequest(BaseModel):
    set_number: SetNumber = Field(..., min_length=1, max_length=32)
    user_goal: UserGoal
    asking_price: OptionalMoney = Field(default=None, ge=0, decimal_places=2)
    condition: PortfolioConditionValue = PortfolioCondition.UNKNOWN
    shipping_price: Money = Field(default=Decimal("0.00"), ge=0, decimal_places=2)
    marketplace_fee_pct: Decimal = Field(default=Decimal("0.13"), ge=0, le=1)
    target_margin_pct: Decimal = Field(default=Decimal("0.15"), ge=0, le=1)
    purchase_price: OptionalMoney = Field(default=None, ge=0, decimal_places=2)
    quantity: int = Field(default=1, gt=0)
    target_profit_pct: Decimal = Field(default=Decimal("0.25"), ge=0, le=10)
    concentration_percent: Decimal | None = Field(default=None, ge=0, le=100)
    marketplace_supply: int | None = Field(default=None, ge=0)
    supply_reliable: bool | None = None
    demand_signal: str | None = Field(default=None, pattern="^(strong|moderate|weak)$")
    valuation_age_days: int | None = Field(default=None, ge=0)
    manual_valuation_override: ManualValuationOverride | None = None


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
    recommendation_category: str | None = None
    recommendation_confidence: ConfidenceBand | None = None
    weighted_inputs: list[dict] | None = None
    reasons: list[dict] | None = None
    warnings: list[str] | None = None
    valuation_source: str = "market"


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
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
