from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from flipradar.api.schemas.validation import (
    MarketplaceValue,
    Money,
    PriceMetricTypeValue,
    SetNumber,
    SnapshotConditionValue,
)


class PriceSnapshotCreate(BaseModel):
    set_number: SetNumber = Field(..., min_length=1, max_length=32)
    marketplace_name: MarketplaceValue
    condition: SnapshotConditionValue
    currency: str = Field(
        default="USD", min_length=3, max_length=3, pattern=r"^[A-Z]{3}$"
    )
    metric_type: PriceMetricTypeValue
    value: Money = Field(..., ge=0, decimal_places=2)
    sample_size: int = Field(..., ge=0)
    source_payload: dict | None = None
    retrieval_time: datetime | None = None


class PriceSnapshotResponse(BaseModel):
    id: UUID
    lego_set_id: UUID
    marketplace_id: UUID
    condition: str
    currency: str
    metric_type: str
    value: Decimal
    sample_size: int
    source_payload: dict | None
    retrieval_time: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PriceAnalyticsResponse(BaseModel):
    observation_count: int
    series_point_count: int
    latest_value: Decimal | None
    rolling_averages: dict[str, Decimal | None]
    volatility: dict[str, Decimal | int | None]
    marketplace_spread: dict[str, Decimal | int | None]
    liquidity: dict[str, int]
    drawdown: dict[str, Decimal | None]
