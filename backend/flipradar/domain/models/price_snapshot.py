from datetime import datetime
from decimal import Decimal
from uuid import UUID as PyUUID
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flipradar.database.base import Base
from flipradar.database.types import JsonDocument
from flipradar.domain.models.enums import PriceMetricType, SnapshotCondition, sql_values


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"
    __table_args__ = (
        CheckConstraint("value >= 0", name="value_non_negative"),
        CheckConstraint("sample_size >= 0", name="sample_size_non_negative"),
        CheckConstraint("currency = upper(currency)", name="currency_uppercase"),
        CheckConstraint(
            f"condition IN ({sql_values(SnapshotCondition)})",
            name="condition_allowed",
        ),
        CheckConstraint(
            f"metric_type IN ({sql_values(PriceMetricType)})",
            name="metric_type_allowed",
        ),
        UniqueConstraint(
            "lego_set_id",
            "marketplace_id",
            "condition",
            "currency",
            "metric_type",
            "retrieval_time",
            name="uq_price_snapshot_metric_retrieval",
        ),
        Index("ix_price_snapshots_set_retrieval_time", "lego_set_id", "retrieval_time"),
        Index(
            "ix_price_snapshots_set_condition_metric_retrieval",
            "lego_set_id",
            "condition",
            "metric_type",
            "retrieval_time",
        ),
        Index(
            "ix_price_snapshots_marketplace_condition_metric_retrieval",
            "marketplace_id",
            "condition",
            "metric_type",
            "retrieval_time",
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
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    metric_type: Mapped[str] = mapped_column(String(30), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    sample_size: Mapped[int] = mapped_column(nullable=False, default=0)
    source_payload: Mapped[dict | None] = mapped_column(JsonDocument)
    retrieval_time: Mapped[datetime] = mapped_column(
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
