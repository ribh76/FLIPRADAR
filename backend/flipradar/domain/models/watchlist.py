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
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flipradar.database.base import Base
from flipradar.domain.models.enums import ListingStatus, sql_values


class WatchlistItem(Base):
    """A user-owned set or marketplace listing that should be monitored."""

    __tablename__ = "watchlist_items"
    __table_args__ = (
        CheckConstraint(
            "(lego_set_id IS NOT NULL AND marketplace_listing_id IS NULL) OR "
            "(lego_set_id IS NULL AND marketplace_listing_id IS NOT NULL)",
            name="exactly_one_target",
        ),
        CheckConstraint(
            "target_price IS NULL OR target_price >= 0",
            name="target_price_non_negative",
        ),
        CheckConstraint(
            "last_known_listing_price IS NULL OR last_known_listing_price >= 0",
            name="last_known_listing_price_non_negative",
        ),
        CheckConstraint(
            "last_known_listing_status IS NULL OR "
            f"last_known_listing_status IN ({sql_values(ListingStatus)})",
            name="last_known_listing_status_allowed",
        ),
        UniqueConstraint("user_id", "lego_set_id", name="uq_watchlist_items_user_set"),
        UniqueConstraint(
            "user_id",
            "marketplace_listing_id",
            name="uq_watchlist_items_user_listing",
        ),
        Index("ix_watchlist_items_user_saved", "user_id", "saved_at"),
        Index("ix_watchlist_items_lego_set_id", "lego_set_id"),
        Index("ix_watchlist_items_marketplace_listing_id", "marketplace_listing_id"),
    )

    id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    lego_set_id: Mapped[PyUUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("lego_sets.id", ondelete="CASCADE")
    )
    marketplace_listing_id: Mapped[PyUUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("marketplace_listings.id", ondelete="CASCADE")
    )
    target_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    saved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_known_listing_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    last_known_listing_status: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="watchlist_items")
    lego_set = relationship("LegoSet", back_populates="watchlist_items")
    listing = relationship("MarketplaceListing", back_populates="watchlist_items")
    price_history = relationship(
        "WatchlistPriceHistory",
        back_populates="watchlist_item",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class WatchlistPriceHistory(Base):
    """Immutable intelligence snapshot captured whenever a watchlist is evaluated."""

    __tablename__ = "watchlist_price_history"
    __table_args__ = (
        CheckConstraint(
            "listing_price IS NULL OR listing_price >= 0",
            name="listing_price_non_negative",
        ),
        CheckConstraint(
            "fair_value IS NULL OR fair_value >= 0", name="fair_value_non_negative"
        ),
        CheckConstraint(
            "deal_score IS NULL OR deal_score BETWEEN 0 AND 100",
            name="deal_score_valid",
        ),
        CheckConstraint(
            "listing_status IS NULL OR "
            f"listing_status IN ({sql_values(ListingStatus)})",
            name="listing_status_allowed",
        ),
        Index(
            "ix_watchlist_price_history_item_observed",
            "watchlist_item_id",
            "observed_at",
        ),
    )

    id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    watchlist_item_id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("watchlist_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    listing_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    listing_status: Mapped[str | None] = mapped_column(String(20))
    fair_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    discount_percent: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    deal_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    is_under_target: Mapped[bool] = mapped_column(nullable=False, default=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    watchlist_item = relationship("WatchlistItem", back_populates="price_history")
