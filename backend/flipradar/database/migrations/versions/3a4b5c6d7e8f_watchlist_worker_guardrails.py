"""add watchlist monitoring preferences and target history

Revision ID: 3a4b5c6d7e8f
Revises: 2a3b4c5d6e7f
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "3a4b5c6d7e8f"
down_revision: Union[str, Sequence[str], None] = "2a3b4c5d6e7f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "watchlist_price_history", sa.Column("target_price", sa.Numeric(12, 2))
    )
    op.create_table(
        "watchlist_monitoring_preferences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "is_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "monitor_listing_expiration",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "material_price_change_percent",
            sa.Numeric(5, 2),
            server_default=sa.text("10"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "material_price_change_percent > 0 AND material_price_change_percent <= 100",
            name="material_change_percent_valid",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("watchlist_monitoring_preferences")
    op.drop_column("watchlist_price_history", "target_price")
