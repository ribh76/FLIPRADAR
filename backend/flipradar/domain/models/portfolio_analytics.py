from datetime import datetime
from decimal import Decimal
from uuid import UUID as PyUUID
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flipradar.database.base import Base
from flipradar.database.types import JsonDocument


class PortfolioAnalyticsSnapshot(Base):
    """An immutable, user-scoped result of one portfolio analytics refresh."""

    __tablename__ = "portfolio_analytics_snapshots"
    __table_args__ = (
        CheckConstraint("holding_count >= 0", name="holding_count_non_negative"),
        CheckConstraint(
            "valued_holding_count >= 0", name="valued_holding_count_non_negative"
        ),
        CheckConstraint("total_cost_basis >= 0", name="total_cost_basis_non_negative"),
        CheckConstraint(
            "total_market_value >= 0", name="total_market_value_non_negative"
        ),
        Index(
            "ix_portfolio_analytics_snapshots_user_generated_at",
            "user_id",
            "generated_at",
        ),
        Index("ix_portfolio_analytics_snapshots_portfolio_generated_at", "portfolio_id", "generated_at"),
    )

    id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    portfolio_id: Mapped[PyUUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("portfolios.id", ondelete="SET NULL")
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    holding_count: Mapped[int] = mapped_column(Integer, nullable=False)
    valued_holding_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_cost_basis: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total_market_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    summary_metrics: Mapped[dict] = mapped_column(JsonDocument, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user = relationship("User", back_populates="portfolio_analytics_snapshots")
    portfolio = relationship("Portfolio")
    holding_metrics = relationship(
        "PortfolioHoldingAnalytics",
        back_populates="analytics_snapshot",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class PortfolioHoldingAnalytics(Base):
    """Persisted per-holding metrics belonging to an analytics snapshot."""

    __tablename__ = "portfolio_holding_analytics"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("cost_basis >= 0", name="cost_basis_non_negative"),
        CheckConstraint(
            "current_total_value IS NULL OR current_total_value >= 0",
            name="current_total_value_non_negative",
        ),
        CheckConstraint(
            "marketplace_supply IS NULL OR marketplace_supply >= 0",
            name="marketplace_supply_non_negative",
        ),
        Index(
            "ix_portfolio_holding_analytics_snapshot_item",
            "analytics_snapshot_id",
            "portfolio_item_id",
        ),
    )

    id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    analytics_snapshot_id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("portfolio_analytics_snapshots.id", ondelete="CASCADE"),
        nullable=False,
    )
    portfolio_item_id: Mapped[PyUUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("portfolio_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    set_number: Mapped[str] = mapped_column(String(32), nullable=False)
    condition: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_basis: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    current_total_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    performance_percent: Mapped[Decimal | None] = mapped_column(Numeric(9, 2))
    holding_days: Mapped[int | None] = mapped_column(Integer)
    valuation_confidence: Mapped[str] = mapped_column(String(24), nullable=False)
    valuation_stale: Mapped[bool] = mapped_column(Boolean, nullable=False)
    trend_label: Mapped[str] = mapped_column(String(20), nullable=False)
    trend_percent: Mapped[Decimal | None] = mapped_column(Numeric(9, 2))
    marketplace_supply: Mapped[int | None] = mapped_column(Integer)
    supply_reliable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    signal: Mapped[str] = mapped_column(String(24), nullable=False)
    signal_score: Mapped[int] = mapped_column(Integer, nullable=False)
    flags: Mapped[list[str]] = mapped_column(JsonDocument, nullable=False)
    metrics: Mapped[dict] = mapped_column(JsonDocument, nullable=False)

    analytics_snapshot = relationship(
        "PortfolioAnalyticsSnapshot", back_populates="holding_metrics"
    )


class PortfolioAnalysis(Base):
    """Completed user-facing analysis linked to its immutable metric snapshot."""

    __tablename__ = "portfolio_analyses"
    __table_args__ = (
        Index("ix_portfolio_analyses_user_generated_at", "user_id", "generated_at"),
    )

    id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    portfolio_id: Mapped[PyUUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("portfolios.id", ondelete="SET NULL")
    )
    analytics_snapshot_id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("portfolio_analytics_snapshots.id", ondelete="CASCADE"),
        nullable=False,
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    method_version: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    portfolio_context: Mapped[dict] = mapped_column(JsonDocument, nullable=False)
    ai_narrative_status: Mapped[str] = mapped_column(String(32), nullable=False)
    ai_narrative: Mapped[dict | None] = mapped_column(JsonDocument)
    item_recommendations: Mapped[list[dict]] = mapped_column(
        JsonDocument, nullable=False
    )
    confidence_summary: Mapped[dict] = mapped_column(JsonDocument, nullable=False)
    data_quality_warnings: Mapped[list[dict]] = mapped_column(
        JsonDocument, nullable=False
    )
    labels: Mapped[list[str]] = mapped_column(
        JsonDocument, nullable=False, default=list
    )
    annotation: Mapped[str | None] = mapped_column(String(1000))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user = relationship("User", back_populates="portfolio_analyses")
    portfolio = relationship("Portfolio")
    analytics_snapshot = relationship("PortfolioAnalyticsSnapshot")
