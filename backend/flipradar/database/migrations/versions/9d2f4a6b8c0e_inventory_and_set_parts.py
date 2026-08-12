"""add user inventory and set part requirements

Revision ID: 9d2f4a6b8c0e
Revises: 7a8b9c0d1e2f
Create Date: 2026-08-12 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "9d2f4a6b8c0e"
down_revision = "7a8b9c0d1e2f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("set_part_requirements", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("lego_set_id", sa.Uuid(), nullable=False), sa.Column("element_id", sa.Uuid(), nullable=False), sa.Column("quantity", sa.Integer(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False), sa.CheckConstraint("quantity > 0", name="quantity_positive"), sa.ForeignKeyConstraint(["lego_set_id"], ["lego_sets.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["element_id"], ["elements.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("lego_set_id", "element_id", name="set_element_unique"))
    op.create_index("ix_set_part_requirements_lego_set_id", "set_part_requirements", ["lego_set_id"])
    op.create_index("ix_set_part_requirements_element_id", "set_part_requirements", ["element_id"])
    op.create_table("inventory_items", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("user_id", sa.Uuid(), nullable=False), sa.Column("element_id", sa.Uuid(), nullable=False), sa.Column("quantity", sa.Integer(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False), sa.CheckConstraint("quantity >= 0", name="quantity_non_negative"), sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["element_id"], ["elements.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("user_id", "element_id", name="user_element_unique"))
    op.create_index("ix_inventory_items_user_id", "inventory_items", ["user_id"])
    op.create_index("ix_inventory_items_element_id", "inventory_items", ["element_id"])
    op.create_table("checklist_adjustments", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("user_id", sa.Uuid(), nullable=False), sa.Column("requirement_id", sa.Uuid(), nullable=False), sa.Column("manual_adjustment", sa.Integer(), nullable=False, server_default="0"), sa.Column("substitute_element_id", sa.Uuid(), nullable=True), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False), sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["requirement_id"], ["set_part_requirements.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["substitute_element_id"], ["elements.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("user_id", "requirement_id", name="user_requirement_unique"))
    op.create_index("ix_checklist_adjustments_user_id", "checklist_adjustments", ["user_id"])
    op.create_index("ix_checklist_adjustments_requirement_id", "checklist_adjustments", ["requirement_id"])


def downgrade() -> None:
    op.drop_table("checklist_adjustments")
    op.drop_table("inventory_items")
    op.drop_table("set_part_requirements")
