from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class LatestSnapshotSummary(BaseModel):
    id: UUID
    condition: str
    currency: str
    low_price: Decimal | None
    median_price: Decimal | None
    average_price: Decimal | None
    high_price: Decimal | None
    fair_market_value: Decimal | None
    listing_count: int
    snapshot_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SetMetadataSummary(BaseModel):
    set_number: str
    name: str
    theme: str | None
    subtheme: str | None
    release_year: int | None
    retirement_year: int | None
    piece_count: int | None
    minifig_count: int | None

    model_config = ConfigDict(from_attributes=True)


class SetDetailResponse(BaseModel):
    metadata: SetMetadataSummary
    set_number: str
    name: str
    theme: str | None
    subtheme: str | None
    release_year: int | None
    retirement_year: int | None
    piece_count: int | None
    minifig_count: int | None
    latest_snapshot: LatestSnapshotSummary | None
    fair_value: Decimal | None
    market_low: Decimal | None
    market_high: Decimal | None
    listing_count: int
    confidence: str | None
    valuation_status: str
