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


class MarketplaceListing(Base):
    __tablename__ = "marketplace_listings"
    __table_args__ = (
        CheckConstraint("price >= 0", name="price_non_negative"),
        CheckConstraint("shipping_price >= 0", name="shipping_price_non_negative"),
        CheckConstraint("total_price >= 0", name="total_price_non_negative"),
        CheckConstraint(
            "total_price = price + shipping_price", name="total_price_matches_parts"
        ),
        CheckConstraint("currency = upper(currency)", name="currency_uppercase"),
        CheckConstraint(
            "condition IN ('new', 'used', 'unknown')", name="condition_allowed"
        ),
        CheckConstraint(
            "listing_status IN ('active', 'sold', 'ended', 'removed')",
            name="listing_status_allowed",
        ),
        CheckConstraint(
            "seller_rating IS NULL OR seller_rating BETWEEN 0 AND 100",
            name="seller_rating_valid",
        ),
        CheckConstraint(
            "match_confidence IS NULL OR match_confidence BETWEEN 0 AND 100",
            name="match_confidence_valid",
        ),
        UniqueConstraint(
            "marketplace_id",
            "external_listing_id",
            name="uq_marketplace_listing_external_id",
        ),
        Index(
            "ix_marketplace_listings_set_status_seen",
            "lego_set_id",
            "listing_status",
            "last_seen_at",
        ),
        Index(
            "ix_marketplace_listings_marketplace_status_seen",
            "marketplace_id",
            "listing_status",
            "last_seen_at",
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
    external_listing_id: Mapped[str] = mapped_column(String(160), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    shipping_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )
    total_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    condition: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unknown"
    )
    listing_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    seller_name: Mapped[str | None] = mapped_column(String(255))
    seller_rating: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    is_complete: Mapped[bool | None] = mapped_column()
    is_sealed: Mapped[bool | None] = mapped_column()
    match_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    raw_payload: Mapped[dict | None] = mapped_column(JsonDocument)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
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

    lego_set = relationship("LegoSet", back_populates="listings")
    marketplace = relationship("Marketplace", back_populates="listings")
