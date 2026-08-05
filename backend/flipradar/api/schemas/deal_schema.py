from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from flipradar.api.schemas.common_schema import PaginationMeta


class DealMarketplaceDetails(BaseModel):
    name: str
    display_name: str
    base_url: str | None
    seller_name: str | None
    seller_rating: Decimal | None


class DealRefreshStatus(BaseModel):
    requested: bool
    cached: bool
    throttled: bool
    retry_after_seconds: int | None = None
    provider_errors: list[str] = Field(default_factory=list)


class DealResponse(BaseModel):
    """One eligible marketplace listing ranked as a flip opportunity."""

    listing_id: UUID
    set_number: str
    set_name: str
    marketplace: DealMarketplaceDetails
    title: str
    url: str
    condition: str
    asking_price: Decimal
    shipping_price: Decimal
    total_cost: Decimal
    currency: str
    fair_value: Decimal
    value: Decimal
    valuation_sample_size: int
    score: int = Field(..., ge=0, le=100)
    deal_band: str
    confidence_score: int = Field(..., ge=0, le=100)
    confidence: int = Field(..., ge=0, le=100)
    discount_percent: Decimal
    discount: Decimal
    last_seen_at: datetime
    explanation: str

    model_config = ConfigDict(from_attributes=True)


class DealCollectionResponse(BaseModel):
    data: list[DealResponse]
    pagination: PaginationMeta
    refresh: DealRefreshStatus
