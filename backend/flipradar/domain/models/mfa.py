from datetime import datetime
from uuid import UUID as PyUUID
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flipradar.database.base import Base


class MfaChallenge(Base):
    __tablename__ = "mfa_challenges"
    __table_args__ = (Index("ix_mfa_challenges_expires_at", "expires_at"),)

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
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    security_question_id: Mapped[str] = mapped_column(String(40), nullable=False)
    failed_attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user = relationship("User", back_populates="mfa_challenges")


class MfaSecurityQuestion(Base):
    __tablename__ = "mfa_security_questions"
    __table_args__ = (
        Index(
            "ix_mfa_security_questions_user_question",
            "user_id",
            "question_id",
            unique=True,
        ),
    )

    id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[str] = mapped_column(String(40), nullable=False)
    answer_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user = relationship("User", back_populates="mfa_security_questions")


class MfaTokenBlacklist(Base):
    __tablename__ = "mfa_token_blacklist"
    __table_args__ = (Index("ix_mfa_token_blacklist_created_at", "created_at"),)

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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user = relationship("User", back_populates="used_mfa_tokens")
