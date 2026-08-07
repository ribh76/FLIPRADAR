from datetime import datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID as PyUUID
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flipradar.database.base import Base
from flipradar.domain.models.enums import NotificationType, sql_values


class Notification(Base):
    """Base event stored for user-facing watchlist notifications."""

    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            f"notification_type IN ({sql_values(NotificationType)})",
            name="notification_type_allowed",
        ),
    )

    id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    watchlist_item_id: Mapped[PyUUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("watchlist_items.id", ondelete="SET NULL")
    )
    notification_type: Mapped[str] = mapped_column(String(32), nullable=False)
    event_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    dedupe_key: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    action_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    is_in_app: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user = relationship("User", back_populates="notifications")
    watchlist_item = relationship("WatchlistItem", back_populates="notifications")
    audit_logs = relationship(
        "NotificationAuditLog",
        back_populates="notification",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __mapper_args__ = {
        "polymorphic_on": notification_type,
        "polymorphic_identity": "notification",
    }


class PriceDropNotification(Notification):
    __tablename__ = "price_drop_notifications"

    id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("notifications.id", ondelete="CASCADE"),
        primary_key=True,
    )
    previous_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    current_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    drop_percent: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)

    __mapper_args__ = {"polymorphic_identity": NotificationType.PRICE_DROP.value}


class TargetReachedNotification(Notification):
    __tablename__ = "target_reached_notifications"

    id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("notifications.id", ondelete="CASCADE"),
        primary_key=True,
    )
    target_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    current_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    __mapper_args__ = {"polymorphic_identity": NotificationType.TARGET_REACHED.value}


class EndedListingNotification(Notification):
    __tablename__ = "ended_listing_notifications"

    id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("notifications.id", ondelete="CASCADE"),
        primary_key=True,
    )
    listing_status: Mapped[str] = mapped_column(String(20), nullable=False)

    __mapper_args__ = {"polymorphic_identity": NotificationType.ENDED_LISTING.value}


class DealScoreNotification(Notification):
    __tablename__ = "deal_score_notifications"

    id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("notifications.id", ondelete="CASCADE"),
        primary_key=True,
    )
    previous_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    current_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)

    __mapper_args__ = {"polymorphic_identity": NotificationType.DEAL_SCORE.value}


class NotificationPreference(Base):
    """Per-user, per-notification-type delivery settings."""

    __tablename__ = "notification_preferences"
    __table_args__ = (
        CheckConstraint(
            f"notification_type IN ({sql_values(NotificationType)})",
            name="notification_preference_type_allowed",
        ),
    )

    id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    notification_type: Mapped[str] = mapped_column(String(32), nullable=False)
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="notification_preferences")


class UserNotificationSettings(Base):
    """Global delivery controls shared across all notification types."""

    __tablename__ = "user_notification_settings"
    __table_args__ = (
        CheckConstraint(
            "(quiet_hours_start IS NULL AND quiet_hours_end IS NULL) OR "
            "(quiet_hours_start IS NOT NULL AND quiet_hours_end IS NOT NULL)",
            name="quiet_hours_complete_range",
        ),
    )

    id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    quiet_hours_start: Mapped[time | None] = mapped_column()
    quiet_hours_end: Mapped[time | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="notification_settings")


class NotificationAuditLog(Base):
    """Append-only record of notification creation, suppression, and delivery."""

    __tablename__ = "notification_audit_logs"

    id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    notification_id: Mapped[PyUUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("notifications.id", ondelete="CASCADE")
    )
    event: Mapped[str] = mapped_column(String(64), nullable=False)
    channel: Mapped[str | None] = mapped_column(String(32))
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    notification = relationship("Notification", back_populates="audit_logs")
    user = relationship("User", back_populates="notification_audit_logs")
