"""Persistent catalog records used to identify individual LEGO parts.

An :class:`Element` represents a provider's sellable part/color combination.
This lets a part expose its available colors through normalized catalog data
instead of keeping a second, denormalized color list.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any
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
    Uuid,
    func,
)
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flipradar.database.base import Base
from flipradar.database.types import JsonDocument


class CatalogRecordMetadata:
    """Shared provider-sourced descriptive fields for part catalog records."""

    provider_identifiers: Mapped[dict[str, str]] = mapped_column(
        JsonDocument, nullable=False, default=dict
    )
    canonical_identifier: Mapped[str] = mapped_column(
        String(160), nullable=False, unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(
        JsonDocument, nullable=False, default=list
    )
    mold_variants: Mapped[list[dict[str, Any]]] = mapped_column(
        JsonDocument, nullable=False, default=list
    )
    image_urls: Mapped[list[str]] = mapped_column(
        JsonDocument, nullable=False, default=list
    )
    quality_flags: Mapped[list[str]] = mapped_column(
        JsonDocument, nullable=False, default=list
    )
    first_known_year: Mapped[int | None] = mapped_column(Integer)
    last_known_year: Mapped[int | None] = mapped_column(Integer)
    source_name: Mapped[str | None] = mapped_column(String(120))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class PartCategory(CatalogRecordMetadata, Base):
    __tablename__ = "part_categories"
    __table_args__ = (
        CheckConstraint(
            "first_known_year IS NULL OR first_known_year BETWEEN 1949 AND 2100",
            name="first_known_year_valid",
        ),
        CheckConstraint(
            "last_known_year IS NULL OR last_known_year BETWEEN 1949 AND 2100",
            name="last_known_year_valid",
        ),
        CheckConstraint(
            "last_known_year IS NULL OR first_known_year IS NULL OR last_known_year >= first_known_year",
            name="known_year_range_valid",
        ),
        Index("ix_part_categories_name", "name"),
    )

    id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )

    parts: Mapped[list[Part]] = relationship(back_populates="category")


class Color(CatalogRecordMetadata, Base):
    __tablename__ = "colors"
    __table_args__ = (
        CheckConstraint(
            "first_known_year IS NULL OR first_known_year BETWEEN 1949 AND 2100",
            name="first_known_year_valid",
        ),
        CheckConstraint(
            "last_known_year IS NULL OR last_known_year BETWEEN 1949 AND 2100",
            name="last_known_year_valid",
        ),
        CheckConstraint(
            "last_known_year IS NULL OR first_known_year IS NULL OR last_known_year >= first_known_year",
            name="known_year_range_valid",
        ),
        Index("ix_colors_name", "name"),
    )

    id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )

    elements: Mapped[list[Element]] = relationship(back_populates="color")


class Part(CatalogRecordMetadata, Base):
    __tablename__ = "parts"
    __table_args__ = (
        CheckConstraint(
            "first_known_year IS NULL OR first_known_year BETWEEN 1949 AND 2100",
            name="first_known_year_valid",
        ),
        CheckConstraint(
            "last_known_year IS NULL OR last_known_year BETWEEN 1949 AND 2100",
            name="last_known_year_valid",
        ),
        CheckConstraint(
            "last_known_year IS NULL OR first_known_year IS NULL OR last_known_year >= first_known_year",
            name="known_year_range_valid",
        ),
        Index("ix_parts_category_id_name", "category_id", "name"),
        Index("ix_parts_name", "name"),
    )

    id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    category_id: Mapped[PyUUID | None] = mapped_column(
        ForeignKey("part_categories.id", ondelete="RESTRICT"), index=True
    )
    market_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    market_price_currency: Mapped[str | None] = mapped_column(String(3))

    category: Mapped[PartCategory | None] = relationship(back_populates="parts")
    elements: Mapped[list[Element]] = relationship(
        back_populates="part", cascade="all, delete-orphan", passive_deletes=True
    )
    available_colors = association_proxy("elements", "color")


class Element(CatalogRecordMetadata, Base):
    __tablename__ = "elements"
    __table_args__ = (
        CheckConstraint(
            "first_known_year IS NULL OR first_known_year BETWEEN 1949 AND 2100",
            name="first_known_year_valid",
        ),
        CheckConstraint(
            "last_known_year IS NULL OR last_known_year BETWEEN 1949 AND 2100",
            name="last_known_year_valid",
        ),
        CheckConstraint(
            "last_known_year IS NULL OR first_known_year IS NULL OR last_known_year >= first_known_year",
            name="known_year_range_valid",
        ),
        Index("ix_elements_part_id_color_id", "part_id", "color_id"),
        Index("ix_elements_name", "name"),
    )

    id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    part_id: Mapped[PyUUID] = mapped_column(
        ForeignKey("parts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    color_id: Mapped[PyUUID] = mapped_column(
        ForeignKey("colors.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    part: Mapped[Part] = relationship(back_populates="elements")
    color: Mapped[Color] = relationship(back_populates="elements")
