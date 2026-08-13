from datetime import datetime
from decimal import Decimal
from typing import Literal
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
    portfolio_id: UUID | None = None
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
    portfolio_id: UUID | None = None
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
    portfolio_id: UUID
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
    theme: str | None = None
    current_unit_value: Decimal | None = None
    current_total_value: Decimal | None = None
    cost_basis: Decimal
    unrealized_gain_loss: Decimal | None = None
    unrealized_gain_loss_percent: Decimal | None = None
    valuation_status: str
    valuation_confidence: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PortfolioCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    currency: str = Field(
        default="USD", min_length=3, max_length=3, pattern=r"^[A-Z]{3}$"
    )


class PortfolioUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    currency: str | None = Field(
        default=None, min_length=3, max_length=3, pattern=r"^[A-Z]{3}$"
    )


class PortfolioResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    description: str | None
    currency: str
    is_default: bool
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PortfolioReassignment(BaseModel):
    target_portfolio_id: UUID


class PortfolioImportRequest(BaseModel):
    """A CSV file is posted as text after the browser has read the uploaded file."""

    csv_content: str = Field(..., min_length=1, max_length=5_000_000)
    duplicate_handling: Literal["keep_separate", "merge", "reject"] = "keep_separate"


class PortfolioImportPreviewRow(BaseModel):
    row_number: int
    set_number: str
    set_name: str
    quantity: int
    purchase_price: Decimal
    currency: str
    action: Literal["create", "merge"]


class PortfolioImportPreviewResponse(BaseModel):
    portfolio_name: str
    portfolio_description: str | None
    portfolio_currency: str
    source_rows: int
    items_to_create: int
    merged_rows: int
    duplicate_handling: str
    changes: list[PortfolioImportPreviewRow]


class PortfolioImportResponse(PortfolioImportPreviewResponse):
    portfolio: PortfolioResponse


class PortfolioHoldingSummary(BaseModel):
    set_number: str
    set_name: str | None
    condition: str
    quantity: int
    cost_basis: Decimal
    estimated_current_value: Decimal | None
    unrealized_gain_loss: Decimal | None
    unrealized_gain_loss_percent: Decimal | None
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


class PortfolioValuationHistoryPoint(BaseModel):
    timestamp: datetime
    cost_basis: Decimal
    market_value: Decimal
    gain_loss: Decimal
    currency: str


class PortfolioValuationHistoryResponse(BaseModel):
    range: str
    points: list[PortfolioValuationHistoryPoint]


class PortfolioDashboardResponse(BaseModel):
    portfolio: dict
    summary: PortfolioSummaryResponse
    history: PortfolioValuationHistoryResponse | None = None
    history_unavailable: str | None = None


class PortfolioAnalyticsHoldingResponse(BaseModel):
    portfolio_item_id: UUID | None
    set_number: str
    condition: str
    quantity: int
    cost_basis: Decimal
    current_total_value: Decimal | None
    performance_percent: Decimal | None
    holding_days: int | None
    valuation_confidence: str
    valuation_stale: bool
    trend_label: str
    trend_percent: Decimal | None
    marketplace_supply: int | None
    supply_reliable: bool
    signal: str
    signal_score: int
    flags: list[str]
    metrics: dict


class PortfolioAnalyticsResponse(BaseModel):
    id: UUID
    generated_at: datetime
    currency: str
    schema_version: int
    holding_count: int
    valued_holding_count: int
    total_cost_basis: Decimal
    total_market_value: Decimal
    summary_metrics: dict
    holdings: list[PortfolioAnalyticsHoldingResponse]


class HoldingMarketSnapshot(BaseModel):
    timestamp: datetime
    marketplace: str
    condition: str
    metric_type: str
    value: Decimal
    sample_size: int
    currency: str


class HoldingConditionPrice(BaseModel):
    condition: str
    estimated_unit_value: Decimal | None
    confidence: str | None
    latest_snapshot_at: datetime | None


class HoldingConcentrationRisk(BaseModel):
    level: str
    message: str
    portfolio_share_percent: Decimal | None
    value_rank: int | None


class PortfolioHoldingDetailResponse(BaseModel):
    holding: PortfolioItemResponse
    portfolio_total_value: Decimal
    portfolio_share_percent: Decimal | None
    concentration_risk: HoldingConcentrationRisk
    market_freshness_at: datetime | None
    market_snapshots: list[HoldingMarketSnapshot]
    condition_pricing: list[HoldingConditionPrice]
