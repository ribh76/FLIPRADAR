from datetime import datetime
from decimal import Decimal
from uuid import UUID as PyUUID, uuid4

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

from database.db import Base
from database.types import JsonDocument


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
        CheckConstraint("currency = upper(currency)", name="currency_uppercase"),
        CheckConstraint(
            "condition IN ('new', 'used', 'mixed', 'unknown')", name="condition_allowed"
        ),
        UniqueConstraint(
            "lego_set_id",
            "marketplace_id",
            "condition",
            "snapshot_at",
            name="uq_price_snapshot_market_condition_time",
        ),
        Index("ix_price_snapshots_set_snapshot_at", "lego_set_id", "snapshot_at"),
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

    lego_set = relationship("LegoSet", back_populates="price_snapshots")
    marketplace = relationship("Marketplace", back_populates="price_snapshots")
