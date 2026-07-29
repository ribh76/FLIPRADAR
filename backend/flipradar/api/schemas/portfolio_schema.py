from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from flipradar.api.schemas.validation import (
    Money,
    OptionalMoney,
    PortfolioConditionValue,
    SetNumber,
)
from flipradar.domain.models.enums import PortfolioCondition


class PortfolioItemCreate(BaseModel):
    set_number: SetNumber = Field(..., min_length=1, max_length=32)
    quantity: int = Field(default=1, gt=0)
    purchase_price: Money = Field(..., ge=0, decimal_places=2)
    condition: PortfolioConditionValue = PortfolioCondition.UNKNOWN
    purchase_date: datetime | None = None
    currency: str = Field(
        default="USD", min_length=3, max_length=3, pattern=r"^[A-Z]{3}$"
    )
    notes: str | None = Field(default=None, max_length=2000)


class PortfolioItemUpdate(BaseModel):
    set_number: SetNumber | None = Field(default=None, min_length=1, max_length=32)
    quantity: int | None = Field(default=None, gt=0)
    purchase_price: OptionalMoney = Field(default=None, ge=0, decimal_places=2)
    condition: PortfolioConditionValue | None = None
    purchase_date: datetime | None = None
    currency: str | None = Field(
        default=None, min_length=3, max_length=3, pattern=r"^[A-Z]{3}$"
    )
    notes: str | None = Field(default=None, max_length=2000)


class PortfolioItemResponse(BaseModel):
    id: UUID
    user_id: UUID
    set_number: str
    quantity: int
    purchase_price: Decimal
    condition: str
    purchase_date: datetime | None
    currency: str
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
    condition: str
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
