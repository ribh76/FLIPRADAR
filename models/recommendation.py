from datetime import datetime
from decimal import Decimal
from uuid import UUID as PyUUID, uuid4

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

from database.db import Base
from database.types import JsonDocument


class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        CheckConstraint(
            "goal IN ('buy_set', 'sell_set', 'hold_vs_sell', 'buy_vs_pass')",
            name="goal_allowed",
        ),
        CheckConstraint(
            "decision IN ('BUY', 'PASS', 'SELL', 'HOLD', 'WATCH')",
            name="decision_allowed",
        ),
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 100",
            name="confidence_score_valid",
        ),
        CheckConstraint(
            "asking_price IS NULL OR asking_price >= 0",
            name="asking_price_non_negative",
        ),
        CheckConstraint(
            "fair_market_value IS NULL OR fair_market_value >= 0",
            name="fair_market_value_non_negative",
        ),
        Index(
            "ix_recommendations_set_goal_created", "lego_set_id", "goal", "created_at"
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
    goal: Mapped[str] = mapped_column(String(40), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    asking_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    fair_market_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    market_summary: Mapped[dict | None] = mapped_column(JsonDocument)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    lego_set = relationship("LegoSet", back_populates="recommendations")
