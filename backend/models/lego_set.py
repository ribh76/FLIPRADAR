from datetime import datetime
from uuid import UUID as PyUUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base


class LegoSet(Base):
    __tablename__ = "lego_sets"
    __table_args__ = (
        CheckConstraint(
            "set_number = upper(trim(set_number))", name="set_number_canonical"
        ),
        CheckConstraint(
            "piece_count IS NULL OR piece_count >= 0", name="piece_count_non_negative"
        ),
        CheckConstraint(
            "minifig_count IS NULL OR minifig_count >= 0",
            name="minifig_count_non_negative",
        ),
        CheckConstraint(
            "release_year IS NULL OR release_year BETWEEN 1949 AND 2100",
            name="release_year_valid",
        ),
        CheckConstraint(
            "retirement_year IS NULL OR retirement_year BETWEEN release_year AND 2100",
            name="retirement_year_valid",
        ),
        Index("ix_lego_sets_theme_release_year", "theme", "release_year"),
    )

    id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    set_number: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    theme: Mapped[str | None] = mapped_column(String(120))
    subtheme: Mapped[str | None] = mapped_column(String(120))
    release_year: Mapped[int | None] = mapped_column(Integer)
    retirement_year: Mapped[int | None] = mapped_column(Integer)
    piece_count: Mapped[int | None] = mapped_column(Integer)
    minifig_count: Mapped[int | None] = mapped_column(Integer)
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
        "MarketplaceListing", back_populates="lego_set", cascade="all, delete-orphan"
    )
    price_snapshots = relationship(
        "PriceSnapshot", back_populates="lego_set", cascade="all, delete-orphan"
    )
    recommendations = relationship(
        "Recommendation", back_populates="lego_set", cascade="all, delete-orphan"
    )
    portfolio_items = relationship("PortfolioItem", back_populates="lego_set")
