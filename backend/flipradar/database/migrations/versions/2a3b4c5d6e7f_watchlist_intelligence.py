"""add watchlist intelligence history

Revision ID: 2a3b4c5d6e7f
Revises: 1a2b3c4d5e6f
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "2a3b4c5d6e7f"
down_revision: Union[str, Sequence[str], None] = "1a2b3c4d5e6f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "watchlist_price_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("watchlist_item_id", sa.Uuid(), nullable=False),
        sa.Column("listing_price", sa.Numeric(12, 2)),
        sa.Column("listing_status", sa.String(20)),
        sa.Column("fair_value", sa.Numeric(12, 2)),
        sa.Column("discount_percent", sa.Numeric(7, 2)),
        sa.Column("deal_score", sa.Numeric(5, 2)),
        sa.Column("is_under_target", sa.Boolean(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "listing_price IS NULL OR listing_price >= 0",
            name="listing_price_non_negative",
        ),
        sa.CheckConstraint(
            "fair_value IS NULL OR fair_value >= 0", name="fair_value_non_negative"
        ),
        sa.CheckConstraint(
            "deal_score IS NULL OR deal_score BETWEEN 0 AND 100",
            name="deal_score_valid",
        ),
        sa.CheckConstraint(
            "listing_status IS NULL OR listing_status IN ('active', 'sold', 'ended', 'removed')",
            name="listing_status_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["watchlist_item_id"], ["watchlist_items.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_watchlist_price_history_item_observed",
        "watchlist_price_history",
        ["watchlist_item_id", "observed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_watchlist_price_history_item_observed", table_name="watchlist_price_history"
    )
    op.drop_table("watchlist_price_history")
