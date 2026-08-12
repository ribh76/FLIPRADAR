"""add replacement purchase tracking

Revision ID: 0e3f5a7b9c1d
Revises: 9d2f4a6b8c0e
Create Date: 2026-08-12 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0e3f5a7b9c1d"
down_revision = "9d2f4a6b8c0e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "replacement_purchase_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_id", sa.Uuid(), nullable=False),
        sa.Column("element_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column(
            "estimated_unit_cost", sa.Float(), nullable=False, server_default="0"
        ),
        sa.Column("actual_unit_cost", sa.Float(), nullable=True),
        sa.Column("purchased", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("quantity > 0", name="quantity_positive"),
        sa.CheckConstraint(
            "estimated_unit_cost >= 0", name="estimated_cost_non_negative"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["requirement_id"], ["set_part_requirements.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["element_id"], ["elements.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "requirement_id", name="user_purchase_requirement_unique"
        ),
    )
    op.create_index(
        "ix_replacement_purchase_items_user_id",
        "replacement_purchase_items",
        ["user_id"],
    )
    op.create_index(
        "ix_replacement_purchase_items_requirement_id",
        "replacement_purchase_items",
        ["requirement_id"],
    )


def downgrade() -> None:
    op.drop_table("replacement_purchase_items")
