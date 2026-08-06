"""add manual watchlist items

Revision ID: 1a2b3c4d5e6f
Revises: f9a2b3c4d5e6
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "1a2b3c4d5e6f"
down_revision: Union[str, Sequence[str], None] = "f9a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "watchlist_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("lego_set_id", sa.Uuid()),
        sa.Column("marketplace_listing_id", sa.Uuid()),
        sa.Column("target_price", sa.Numeric(precision=12, scale=2)),
        sa.Column("notes", sa.Text()),
        sa.Column(
            "saved_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("last_known_listing_price", sa.Numeric(precision=12, scale=2)),
        sa.Column("last_known_listing_status", sa.String(length=20)),
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
            "(lego_set_id IS NOT NULL AND marketplace_listing_id IS NULL) OR "
            "(lego_set_id IS NULL AND marketplace_listing_id IS NOT NULL)",
            name="exactly_one_target",
        ),
        sa.CheckConstraint(
            "target_price IS NULL OR target_price >= 0",
            name="target_price_non_negative",
        ),
        sa.CheckConstraint(
            "last_known_listing_price IS NULL OR last_known_listing_price >= 0",
            name="last_known_listing_price_non_negative",
        ),
        sa.CheckConstraint(
            "last_known_listing_status IS NULL OR last_known_listing_status IN "
            "('active', 'sold', 'ended', 'removed')",
            name="last_known_listing_status_allowed",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lego_set_id"], ["lego_sets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["marketplace_listing_id"], ["marketplace_listings.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "lego_set_id", name="uq_watchlist_items_user_set"
        ),
        sa.UniqueConstraint(
            "user_id",
            "marketplace_listing_id",
            name="uq_watchlist_items_user_listing",
        ),
    )
    op.create_index(
        "ix_watchlist_items_user_saved", "watchlist_items", ["user_id", "saved_at"]
    )
    op.create_index(
        "ix_watchlist_items_lego_set_id", "watchlist_items", ["lego_set_id"]
    )
    op.create_index(
        "ix_watchlist_items_marketplace_listing_id",
        "watchlist_items",
        ["marketplace_listing_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_watchlist_items_marketplace_listing_id", table_name="watchlist_items"
    )
    op.drop_index("ix_watchlist_items_lego_set_id", table_name="watchlist_items")
    op.drop_index("ix_watchlist_items_user_saved", table_name="watchlist_items")
    op.drop_table("watchlist_items")
