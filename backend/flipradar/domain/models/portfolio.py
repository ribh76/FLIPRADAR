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
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flipradar.database.base import Base
from flipradar.domain.models.enums import PortfolioCondition, sql_values


class Portfolio(Base):
    __tablename__ = "portfolios"
    __table_args__ = (
        CheckConstraint("currency = upper(currency)", name="currency_uppercase"),
        Index("ix_portfolios_user_id", "user_id"),
        Index("ix_portfolios_user_created_at", "user_id", "created_at"),
    )

    id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    is_default: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user = relationship("User", back_populates="portfolios")
    items = relationship("PortfolioItem", back_populates="portfolio")


class PortfolioItem(Base):
    __tablename__ = "portfolio_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("purchase_price >= 0", name="purchase_price_non_negative"),
        CheckConstraint("currency = upper(currency)", name="currency_uppercase"),
        CheckConstraint(
            f"condition IN ({sql_values(PortfolioCondition)})",
            name="condition_allowed",
        ),
        Index("ix_portfolio_items_user_id", "user_id"),
        Index("ix_portfolio_items_portfolio_id", "portfolio_id"),
        Index("ix_portfolio_items_lego_set_id", "lego_set_id"),
        Index("ix_portfolio_items_user_lego_set", "user_id", "lego_set_id"),
        Index("ix_portfolio_items_user_created_at", "user_id", "created_at"),
    )

    id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    portfolio_id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="RESTRICT"),
        nullable=False,
    )
    lego_set_id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("lego_sets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    condition: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unknown"
    )
    purchase_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
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
    portfolio = relationship("Portfolio", back_populates="items")
    lego_set = relationship("LegoSet", back_populates="portfolio_items")
    valuation_snapshots = relationship(
        "PortfolioItemValuationSnapshot",
        back_populates="portfolio_item",
        passive_deletes=True,
    )

    @property
    def set_number(self) -> str:
        return self.lego_set.set_number


class PortfolioImportAuditLog(Base):
    """Immutable record of a completed CSV import; file contents are never stored."""

    __tablename__ = "portfolio_import_audit_logs"
    __table_args__ = (
        CheckConstraint("source_rows > 0", name="source_rows_positive"),
        CheckConstraint("items_created >= 0", name="items_created_non_negative"),
        CheckConstraint("merged_rows >= 0", name="merged_rows_non_negative"),
        Index("ix_portfolio_import_audit_user_created", "user_id", "created_at"),
    )

    id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    portfolio_id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    items_created: Mapped[int] = mapped_column(Integer, nullable=False)
    merged_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    duplicate_handling: Mapped[str] = mapped_column(String(20), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user = relationship("User", back_populates="portfolio_import_audit_logs")
    portfolio = relationship("Portfolio")
