from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.validation import (
    MarketplaceValue,
    Money,
    OptionalMoney,
    SetNumber,
    SnapshotConditionValue,
)


class PriceSnapshotCreate(BaseModel):
    set_number: SetNumber = Field(..., min_length=1, max_length=32)
    marketplace_name: MarketplaceValue
    condition: SnapshotConditionValue = "unknown"
    currency: str = Field(
        default="USD", min_length=3, max_length=3, pattern=r"^[A-Z]{3}$"
    )
    low_price: OptionalMoney = Field(default=None, ge=0, decimal_places=2)
    median_price: OptionalMoney = Field(default=None, ge=0, decimal_places=2)
    average_price: OptionalMoney = Field(default=None, ge=0, decimal_places=2)
    high_price: OptionalMoney = Field(default=None, ge=0, decimal_places=2)
    fair_market_value: OptionalMoney = Field(default=None, ge=0, decimal_places=2)
    listing_count: int = Field(default=0, ge=0)
    source_payload: dict | None = None
    snapshot_at: datetime | None = None

    @model_validator(mode="after")
    def validate_snapshot_values(self):
        if self.low_price is not None and self.high_price is not None:
            if self.low_price > self.high_price:
                raise ValueError("low_price must be less than or equal to high_price")
        for field_name in ("median_price", "average_price", "fair_market_value"):
            value = getattr(self, field_name)
            if value is None:
                continue
            if self.low_price is not None and value < self.low_price:
                raise ValueError(
                    f"{field_name} must be greater than or equal to low_price"
                )
            if self.high_price is not None and value > self.high_price:
                raise ValueError(
                    f"{field_name} must be less than or equal to high_price"
                )
        return self


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
