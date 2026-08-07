from datetime import datetime
from decimal import Decimal
from uuid import UUID as PyUUID
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flipradar.database.base import Base


class WatchlistMonitoringPreference(Base):
    __tablename__ = "watchlist_monitoring_preferences"
    __table_args__ = (
        CheckConstraint(
            "material_price_change_percent > 0 AND material_price_change_percent <= 100",
            name="material_change_percent_valid",
        ),
    )

    id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    monitor_listing_expiration: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    material_price_change_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=10
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

    user = relationship("User", back_populates="watchlist_monitoring_preference")
