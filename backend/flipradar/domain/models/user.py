from datetime import datetime
from uuid import UUID as PyUUID
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, Uuid, false, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flipradar.database.base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("username = lower(trim(username))", name="username_canonical"),
        CheckConstraint("email = lower(trim(email))", name="email_canonical"),
        CheckConstraint(
            "(email LIKE '%@%.com' OR email LIKE '%@%.org')",
            name="email_supported_domain",
        ),
    )

    id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    username: Mapped[str] = mapped_column(
        String(80), nullable=False, unique=True, index=True
    )
    display_name: Mapped[str | None] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    pending_email: Mapped[str | None] = mapped_column(
        String(255), unique=True, index=True
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_email_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deletion_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    deletion_scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
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

    portfolio_items = relationship(
        "PortfolioItem",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    portfolio_valuation_snapshots = relationship(
        "PortfolioValuationSnapshot",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    portfolio_valuation_daily_rollups = relationship(
        "PortfolioValuationDailyRollup",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    portfolio_analytics_snapshots = relationship(
        "PortfolioAnalyticsSnapshot",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    portfolio_analyses = relationship(
        "PortfolioAnalysis",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    revoked_refresh_tokens = relationship(
        "RefreshTokenBlacklist",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    refresh_token_sessions = relationship(
        "RefreshTokenSession",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    account_tokens = relationship(
        "AccountToken",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    saved_searches = relationship(
        "SavedSearch",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    watchlist_items = relationship(
        "WatchlistItem",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    watchlist_monitoring_preference = relationship(
        "WatchlistMonitoringPreference",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    notifications = relationship(
        "Notification",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    notification_preferences = relationship(
        "NotificationPreference",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    notification_settings = relationship(
        "UserNotificationSettings",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    notification_audit_logs = relationship(
        "NotificationAuditLog",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
