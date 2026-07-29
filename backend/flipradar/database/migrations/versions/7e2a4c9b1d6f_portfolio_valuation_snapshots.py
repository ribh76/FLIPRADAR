"""add portfolio valuation snapshot tables

Revision ID: 7e2a4c9b1d6f
Revises: 0f3a9b7d2c6e
Create Date: 2026-07-29 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "7e2a4c9b1d6f"
down_revision: Union[str, Sequence[str], None] = "0f3a9b7d2c6e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "portfolio_valuation_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("cost_basis", sa.Numeric(12, 2), nullable=False),
        sa.Column("market_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("gain_loss", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "window_start",
            name="uq_portfolio_valuation_snapshots_user_window",
        ),
    )
    op.create_index(
        "ix_portfolio_valuation_snapshots_user_snapshot_at",
        "portfolio_valuation_snapshots",
        ["user_id", "snapshot_at"],
    )
    op.create_table(
        "portfolio_item_valuation_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("portfolio_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("portfolio_item_id", sa.Uuid(), nullable=False),
        sa.Column("unit_value", sa.Numeric(12, 2), nullable=True),
        sa.Column("total_value", sa.Numeric(12, 2), nullable=True),
        sa.Column("confidence", sa.String(20), nullable=False),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["portfolio_snapshot_id"],
            ["portfolio_valuation_snapshots.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["portfolio_item_id"], ["portfolio_items.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "portfolio_snapshot_id",
            "portfolio_item_id",
            name="uq_portfolio_item_valuation_snapshots_snapshot_item",
        ),
    )
    op.create_index(
        "ix_portfolio_item_valuation_snapshots_item_snapshot_at",
        "portfolio_item_valuation_snapshots",
        ["portfolio_item_id", "snapshot_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_portfolio_item_valuation_snapshots_item_snapshot_at",
        table_name="portfolio_item_valuation_snapshots",
    )
    op.drop_table("portfolio_item_valuation_snapshots")
    op.drop_index(
        "ix_portfolio_valuation_snapshots_user_snapshot_at",
        table_name="portfolio_valuation_snapshots",
    )
    op.drop_table("portfolio_valuation_snapshots")
