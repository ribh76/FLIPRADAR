from datetime import datetime
from decimal import Decimal
from uuid import UUID as PyUUID
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flipradar.database.base import Base
from flipradar.database.types import JsonDocument
from flipradar.domain.models.enums import SnapshotCondition, sql_values


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"
    __table_args__ = (
        CheckConstraint(
            "low_price IS NULL OR low_price >= 0", name="low_price_non_negative"
        ),
        CheckConstraint(
            "median_price IS NULL OR median_price >= 0",
            name="median_price_non_negative",
        ),
        CheckConstraint(
            "average_price IS NULL OR average_price >= 0",
            name="average_price_non_negative",
        ),
        CheckConstraint(
            "high_price IS NULL OR high_price >= 0", name="high_price_non_negative"
        ),
        CheckConstraint(
            "fair_market_value IS NULL OR fair_market_value >= 0",
            name="fair_market_value_non_negative",
        ),
        CheckConstraint("listing_count >= 0", name="listing_count_non_negative"),
        CheckConstraint(
            "low_price IS NULL OR high_price IS NULL OR low_price <= high_price",
            name="price_range_ordered",
        ),
        CheckConstraint(
            "low_price IS NULL OR median_price IS NULL OR low_price <= median_price",
            name="median_price_above_low",
        ),
        CheckConstraint(
            "high_price IS NULL OR median_price IS NULL OR median_price <= high_price",
            name="median_price_below_high",
        ),
        CheckConstraint(
            "low_price IS NULL OR average_price IS NULL OR low_price <= average_price",
            name="average_price_above_low",
        ),
        CheckConstraint(
            "high_price IS NULL OR average_price IS NULL OR average_price <= high_price",
            name="average_price_below_high",
        ),
        CheckConstraint(
            "low_price IS NULL OR fair_market_value IS NULL OR low_price <= fair_market_value",
            name="fair_market_value_above_low",
        ),
        CheckConstraint(
            "high_price IS NULL OR fair_market_value IS NULL OR fair_market_value <= high_price",
            name="fair_market_value_below_high",
        ),
        CheckConstraint("currency = upper(currency)", name="currency_uppercase"),
        CheckConstraint(
            f"condition IN ({sql_values(SnapshotCondition)})",
            name="condition_allowed",
        ),
        UniqueConstraint(
            "lego_set_id",
            "marketplace_id",
            "condition",
            "snapshot_at",
            name="uq_price_snapshot_market_condition_time",
        ),
        Index("ix_price_snapshots_set_snapshot_at", "lego_set_id", "snapshot_at"),
        Index(
            "ix_price_snapshots_set_condition_snapshot_at",
            "lego_set_id",
            "condition",
            "snapshot_at",
        ),
        Index(
            "ix_price_snapshots_marketplace_condition_snapshot_at",
            "marketplace_id",
            "condition",
            "snapshot_at",
        ),
    )

    id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    lego_set_id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("lego_sets.id", ondelete="CASCADE"),
        nullable=False,
    )
    marketplace_id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("marketplaces.id", ondelete="RESTRICT"),
        nullable=False,
    )
    condition: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unknown"
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    low_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    median_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    average_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    high_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    fair_market_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    listing_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_payload: Mapped[dict | None] = mapped_column(JsonDocument)
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    lego_set = relationship("LegoSet", back_populates="price_snapshots")
    marketplace = relationship("Marketplace", back_populates="price_snapshots")
