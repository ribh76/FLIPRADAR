from datetime import datetime
from uuid import UUID as PyUUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Numeric, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base


class Marketplace(Base):
    __tablename__ = "marketplaces"
    __table_args__ = (
        CheckConstraint("name = lower(name)", name="name_lowercase"),
        CheckConstraint("name IN ('ebay', 'bricklink')", name="name_allowed"),
        CheckConstraint(
            "fee_percent >= 0 AND fee_percent <= 100", name="fee_percent_valid"
        ),
    )

    id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(
        String(80), nullable=False, unique=True, index=True
    )
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(500))
    fee_percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    listings = relationship(
        "MarketplaceListing", back_populates="marketplace", cascade="all, delete-orphan"
    )
    price_snapshots = relationship(
        "PriceSnapshot", back_populates="marketplace", cascade="all, delete-orphan"
    )
