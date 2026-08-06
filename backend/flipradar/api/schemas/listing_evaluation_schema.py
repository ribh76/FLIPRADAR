from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ListingAnalysisResponse(BaseModel):
    id: UUID
    listing_id: UUID
    fair_value: Decimal | None
    fair_value_low: Decimal | None
    fair_value_high: Decimal | None
    total_cost: Decimal
    discount_percent: Decimal | None
    premium_percent: Decimal | None
    product_match_confidence: Decimal
    decision: str
    decision_confidence: Decimal = Field(..., ge=0, le=100)
    reasons: list[str]
    risk_flags: list[str]
    score_breakdown: dict
    valuation_sample_size: int
    valuation_retrieved_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
