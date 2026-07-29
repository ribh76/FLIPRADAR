from datetime import datetime
from decimal import Decimal
from uuid import UUID as PyUUID
from uuid import uuid4

from sqlalchemy import (
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


class PortfolioValuationSnapshot(Base):
    __tablename__ = "portfolio_valuation_snapshots"
    __table_args__ = (
        UniqueConstraint("user_id", "window_start", name="user_window"),
        Index(
            "ix_portfolio_valuation_snapshots_user_snapshot_at",
            "user_id",
            "snapshot_at",
        ),
    )

    id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    cost_basis: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    market_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    gain_loss: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user = relationship("User", back_populates="portfolio_valuation_snapshots")
    item_snapshots = relationship(
        "PortfolioItemValuationSnapshot",
        back_populates="portfolio_snapshot",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class PortfolioItemValuationSnapshot(Base):
    __tablename__ = "portfolio_item_valuation_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "portfolio_snapshot_id", "portfolio_item_id", name="snapshot_item"
        ),
        Index(
            "ix_portfolio_item_valuation_snapshots_item_snapshot_at",
            "portfolio_item_id",
            "snapshot_at",
        ),
    )

    id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    portfolio_snapshot_id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("portfolio_valuation_snapshots.id", ondelete="CASCADE"),
        nullable=False,
    )
    portfolio_item_id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("portfolio_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    unit_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    total_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    confidence: Mapped[str] = mapped_column(
        String(20), nullable=False, default="missing_market_data"
    )
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    portfolio_snapshot = relationship(
        "PortfolioValuationSnapshot", back_populates="item_snapshots"
    )
    portfolio_item = relationship("PortfolioItem", back_populates="valuation_snapshots")
