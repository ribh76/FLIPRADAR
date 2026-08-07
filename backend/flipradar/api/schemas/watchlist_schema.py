from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from flipradar.api.schemas.validation import OptionalMoney, SetNumber
from flipradar.domain.models.enums import ListingStatus


class WatchlistItemCreate(BaseModel):
    set_number: SetNumber | None = Field(default=None, min_length=1, max_length=32)
    listing_id: UUID | None = None
    target_price: OptionalMoney = Field(default=None, ge=0, decimal_places=2)
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_target(self) -> WatchlistItemCreate:
        if (self.set_number is None) == (self.listing_id is None):
            raise ValueError("Provide exactly one of set_number or listing_id")
        return self


class WatchlistItemUpdate(BaseModel):
    target_price: OptionalMoney = Field(default=None, ge=0, decimal_places=2)
    notes: str | None = Field(default=None, max_length=2000)


class WatchlistMonitoringPreferenceUpdate(BaseModel):
    is_enabled: bool | None = None
    monitor_listing_expiration: bool | None = None
    material_price_change_percent: Decimal | None = Field(
        default=None, gt=0, le=100, decimal_places=2
    )


class WatchlistMonitoringPreferenceResponse(BaseModel):
    is_enabled: bool
    monitor_listing_expiration: bool
    material_price_change_percent: Decimal

    model_config = ConfigDict(from_attributes=True)


class WatchlistItemResponse(BaseModel):
    id: UUID
    user_id: UUID
    entry_type: str
    set_number: str
    listing_id: UUID | None
    target_price: Decimal | None
    notes: str | None
    saved_at: datetime
    last_known_listing_price: Decimal | None
    last_known_listing_status: ListingStatus | None
    current_price: Decimal | None
    valuation: Decimal | None
    discount_percent: Decimal | None
    deal_score: Decimal | None
    price_change: Decimal | None
    is_under_target: bool
    recommendation: str
    last_checked_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WatchlistMoveToPortfolio(BaseModel):
    quantity: int = Field(default=1, gt=0)
    purchase_price: OptionalMoney = Field(default=None, ge=0, decimal_places=2)


class WatchlistSummaryResponse(BaseModel):
    total_entries: int
    under_target_count: int
    price_changed_count: int
    ended_or_removed_count: int
    scored_entries: int
    average_deal_score: Decimal | None


class WatchlistHistoryPoint(BaseModel):
    observed_at: datetime
    listing_price: Decimal | None
    fair_value: Decimal | None
    deal_score: Decimal | None
    listing_status: ListingStatus | None


class WatchlistReplacementResponse(BaseModel):
    listing_id: UUID
    title: str
    url: str
    total_price: Decimal
    currency: str
    fair_value: Decimal | None
    deal_score: Decimal | None
    recommendation: str
