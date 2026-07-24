from datetime import datetime
from uuid import UUID as PyUUID
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flipradar.database.base import Base


class RefreshTokenBlacklist(Base):
    __tablename__ = "refresh_token_blacklist"
    __table_args__ = (
        Index("ix_refresh_token_blacklist_user_id", "user_id"),
        Index("ix_refresh_token_blacklist_expires_at", "expires_at"),
    )

    id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    token_jti: Mapped[str] = mapped_column(
        String(36), nullable=False, unique=True, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    reason: Mapped[str] = mapped_column(String(80), nullable=False)

    user = relationship("User", back_populates="revoked_refresh_tokens")
