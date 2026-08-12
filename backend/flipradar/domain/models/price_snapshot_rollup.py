from datetime import date, datetime
from decimal import Decimal
from uuid import UUID as PyUUID
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
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
from sqlalchemy.orm import Mapped, mapped_column

from flipradar.database.base import Base


class PriceSnapshotRollup(Base):
    """Compacted historical price observations for a calendar week or month."""

    __tablename__ = "price_snapshot_rollups"
    __table_args__ = (
        CheckConstraint("period IN ('weekly', 'monthly')", name="period_allowed"),
        CheckConstraint("observation_count > 0", name="observation_count_positive"),
        CheckConstraint("average_value >= 0", name="average_value_non_negative"),
        CheckConstraint("low_value >= 0", name="low_value_non_negative"),
        CheckConstraint("high_value >= low_value", name="value_range_ordered"),
        UniqueConstraint(
            "lego_set_id",
            "marketplace_id",
            "condition",
            "currency",
            "metric_type",
            "period",
            "period_start",
            name="period",
        ),
        Index(
            "ix_price_snapshot_rollups_set_period_start",
            "lego_set_id",
            "period",
            "period_start",
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
    condition: Mapped[str] = mapped_column(String(20), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    metric_type: Mapped[str] = mapped_column(String(30), nullable=False)
    period: Mapped[str] = mapped_column(String(10), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    average_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    low_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    high_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    latest_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    average_sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    latest_retrieval_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
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
