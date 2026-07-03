from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PortfolioItemCreate(BaseModel):
    set_number: str = Field(..., min_length=1, max_length=32)
    quantity: int = Field(default=1, gt=0)
    purchase_price: Decimal = Field(..., ge=0, decimal_places=2)
    condition: str = Field(default="unknown", pattern=r"^(new|used|sealed|unknown)$")
    acquired_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=2000)


class PortfolioItemResponse(BaseModel):
    id: UUID
    user_id: UUID
    set_number: str
    quantity: int
    purchase_price: Decimal
    condition: str
    acquired_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    set_name: str | None = None
    current_unit_value: Decimal | None = None
    current_total_value: Decimal | None = None
    cost_basis: Decimal
    unrealized_gain_loss: Decimal | None = None
    valuation_status: str

    model_config = ConfigDict(from_attributes=True)


class PortfolioHoldingSummary(BaseModel):
    set_number: str
    set_name: str | None
    quantity: int
    cost_basis: Decimal
    estimated_current_value: Decimal | None
    unrealized_gain_loss: Decimal | None
    valuation_status: str


class PortfolioSummaryResponse(BaseModel):
    total_items: int
    total_sets: int
    total_quantity: int
    total_cost_basis: Decimal
    estimated_current_value: Decimal
    unrealized_gain_loss: Decimal
    unrealized_gain_loss_percent: Decimal | None
    holdings: list[PortfolioHoldingSummary]
