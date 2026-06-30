from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PriceSnapshotCreate(BaseModel):
    set_number: str = Field(..., min_length=1, max_length=32)
    marketplace_name: str = Field(..., min_length=1, max_length=80)
    condition: str = Field(default="unknown", pattern=r"^(new|used|mixed|unknown)$")
    currency: str = Field(
        default="USD", min_length=3, max_length=3, pattern=r"^[A-Z]{3}$"
    )
    low_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    median_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    average_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    high_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    fair_market_value: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    listing_count: int = Field(default=0, ge=0)
    source_payload: dict | None = None
    snapshot_at: datetime | None = None


class PriceSnapshotResponse(BaseModel):
    id: UUID
    lego_set_id: UUID
    marketplace_id: UUID
    condition: str
    currency: str
    low_price: Decimal | None
    median_price: Decimal | None
    average_price: Decimal | None
    high_price: Decimal | None
    fair_market_value: Decimal | None
    listing_count: int
    source_payload: dict | None
    snapshot_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
