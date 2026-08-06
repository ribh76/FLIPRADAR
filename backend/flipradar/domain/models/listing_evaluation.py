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
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flipradar.database.base import Base
from flipradar.database.types import JsonDocument


class ListingEvaluation(Base):
    __tablename__ = "listing_evaluations"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('buy', 'watch', 'pass', 'insufficient_data')",
            name="decision_allowed",
        ),
        CheckConstraint(
            "decision_confidence BETWEEN 0 AND 100", name="decision_confidence_valid"
        ),
        CheckConstraint("total_cost >= 0", name="total_cost_non_negative"),
        Index("ix_listing_evaluations_listing_created", "listing_id", "created_at"),
    )

    id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    listing_id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("marketplace_listings.id", ondelete="CASCADE"),
        nullable=False,
    )
    fair_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    total_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount_percent: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    premium_percent: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    product_match_confidence: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False
    )
    decision: Mapped[str] = mapped_column(String(24), nullable=False)
    decision_confidence: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    reasons: Mapped[list[str]] = mapped_column(JsonDocument, nullable=False)
    risk_flags: Mapped[list[str]] = mapped_column(JsonDocument, nullable=False)
    score_breakdown: Mapped[dict] = mapped_column(JsonDocument, nullable=False)
    valuation_sample_size: Mapped[int] = mapped_column(nullable=False, default=0)
    valuation_retrieved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    listing = relationship("MarketplaceListing", back_populates="evaluations")
