from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from flipradar.api.schemas.validation import (
    ListingConditionValue,
    LowerText,
    MarketplaceValue,
    Money,
    OptionalMoney,
    SetNumber,
)
from flipradar.domain.models.enums import ListingCondition


class MarketplaceCreate(BaseModel):
    name: MarketplaceValue
    display_name: str = Field(..., min_length=1, max_length=120)
    base_url: HttpUrl | None = None
    fee_percent: Money = Field(default=Decimal("0.00"), ge=0, le=100, decimal_places=2)


class MarketplaceResponse(MarketplaceCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ListingCreate(BaseModel):
    set_number: SetNumber = Field(..., min_length=1, max_length=32)
    marketplace_name: MarketplaceValue
    external_listing_id: str = Field(..., min_length=1, max_length=160)
    detected_set_number: SetNumber | None = Field(default=None, max_length=32)
    title: str = Field(..., min_length=1, max_length=500)
    url: HttpUrl
    price: Money = Field(..., ge=0, decimal_places=2)
    shipping_price: Money = Field(default=Decimal("0.00"), ge=0, decimal_places=2)
    total_price: Money = Field(..., ge=0, decimal_places=2)
    currency: str = Field(
        default="USD", min_length=3, max_length=3, pattern=r"^[A-Z]{3}$"
    )
    condition: ListingConditionValue = ListingCondition.UNKNOWN
    listing_status: LowerText = Field(
        default="active", pattern=r"^(active|sold|ended|removed)$"
    )
    seller_name: str | None = Field(default=None, max_length=255)
    seller_rating: OptionalMoney = Field(default=None, ge=0, le=100, decimal_places=2)
    is_complete: bool | None = None
    is_sealed: bool | None = None
    match_confidence: OptionalMoney = Field(
        default=None, ge=0, le=100, decimal_places=2
    )
    match_reasons: list[str] | None = Field(default=None, max_length=32)
    exclusion_flags: list[str] | None = Field(default=None, max_length=32)
    raw_payload: dict | None = None

    @model_validator(mode="after")
    def validate_total_price(self):
        expected_total = self.price + self.shipping_price
        if self.total_price != expected_total:
            raise ValueError("total_price must equal price plus shipping_price")
        return self


class ListingResponse(BaseModel):
    id: UUID
    lego_set_id: UUID
    marketplace_id: UUID
    external_listing_id: str
    detected_set_number: str | None
    title: str
    url: str
    price: Decimal
    shipping_price: Decimal
    total_price: Decimal
    currency: str
    condition: str
    listing_status: str
    seller_name: str | None
    seller_rating: Decimal | None
    is_complete: bool | None
    is_sealed: bool | None
    match_confidence: Decimal | None
    match_reasons: list[str] | None
    exclusion_flags: list[str] | None
    raw_payload: dict | None
    first_seen_at: datetime
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
