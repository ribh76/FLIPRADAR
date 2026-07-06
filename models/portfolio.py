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
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base


class PortfolioItem(Base):
    __tablename__ = "portfolio_items"
    __table_args__ = (
        CheckConstraint(
            "set_number = upper(trim(set_number))", name="set_number_canonical"
        ),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("purchase_price >= 0", name="purchase_price_non_negative"),
        CheckConstraint(
            "condition IN ('new', 'used', 'sealed', 'unknown')",
            name="condition_allowed",
        ),
        Index("ix_portfolio_items_user_id", "user_id"),
        Index("ix_portfolio_items_set_number", "set_number"),
        Index("ix_portfolio_items_user_set", "user_id", "set_number"),
    )

    id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    set_number: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("lego_sets.set_number", ondelete="RESTRICT"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    condition: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unknown"
    )
    acquired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="portfolio_items")
    lego_set = relationship("LegoSet", back_populates="portfolio_items")
