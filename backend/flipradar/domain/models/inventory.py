"""User-owned parts and the set bill-of-materials used for rebuild checklists."""

from datetime import datetime
from uuid import UUID as PyUUID
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flipradar.database.base import Base


class SetPartRequirement(Base):
    __tablename__ = "set_part_requirements"
    __table_args__ = (
        UniqueConstraint("lego_set_id", "element_id", name="set_element_unique"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
    )

    id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    lego_set_id: Mapped[PyUUID] = mapped_column(
        ForeignKey("lego_sets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    element_id: Mapped[PyUUID] = mapped_column(
        ForeignKey("elements.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    lego_set = relationship("LegoSet", back_populates="part_requirements")
    element = relationship("Element")


class InventoryItem(Base):
    __tablename__ = "inventory_items"
    __table_args__ = (
        UniqueConstraint("user_id", "element_id", name="user_element_unique"),
        CheckConstraint("quantity >= 0", name="quantity_non_negative"),
    )

    id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[PyUUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    element_id: Mapped[PyUUID] = mapped_column(
        ForeignKey("elements.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="inventory_items")
    element = relationship("Element")


class ChecklistAdjustment(Base):
    __tablename__ = "checklist_adjustments"
    __table_args__ = (
        UniqueConstraint("user_id", "requirement_id", name="user_requirement_unique"),
    )

    id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[PyUUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requirement_id: Mapped[PyUUID] = mapped_column(
        ForeignKey("set_part_requirements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    manual_adjustment: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    substitute_element_id: Mapped[PyUUID | None] = mapped_column(
        ForeignKey("elements.id", ondelete="RESTRICT")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="checklist_adjustments")
    requirement = relationship("SetPartRequirement")
    substitute_element = relationship("Element", foreign_keys=[substitute_element_id])


class ReplacementPurchaseItem(Base):
    """A planned or completed order for one missing set requirement."""

    __tablename__ = "replacement_purchase_items"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "requirement_id", name="user_purchase_requirement_unique"
        ),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("estimated_unit_cost >= 0", name="estimated_cost_non_negative"),
    )

    id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[PyUUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requirement_id: Mapped[PyUUID] = mapped_column(
        ForeignKey("set_part_requirements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    element_id: Mapped[PyUUID] = mapped_column(
        ForeignKey("elements.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_unit_cost: Mapped[float] = mapped_column(nullable=False, default=0)
    actual_unit_cost: Mapped[float | None] = mapped_column()
    purchased: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="replacement_purchase_items")
    requirement = relationship("SetPartRequirement")
    element = relationship("Element")
