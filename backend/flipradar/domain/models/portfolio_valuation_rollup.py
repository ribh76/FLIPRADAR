from datetime import date, datetime
from decimal import Decimal
from uuid import UUID as PyUUID
from uuid import uuid4

from sqlalchemy import (
    Date,
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


class PortfolioValuationDailyRollup(Base):
    __tablename__ = "portfolio_valuation_daily_rollups"
    __table_args__ = (
        UniqueConstraint("user_id", "rollup_date", name="user_date"),
        Index(
            "ix_portfolio_valuation_daily_rollups_user_date", "user_id", "rollup_date"
        ),
    )

    id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    rollup_date: Mapped[date] = mapped_column(Date, nullable=False)
    cost_basis: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    market_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    gain_loss: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user = relationship("User", back_populates="portfolio_valuation_daily_rollups")
