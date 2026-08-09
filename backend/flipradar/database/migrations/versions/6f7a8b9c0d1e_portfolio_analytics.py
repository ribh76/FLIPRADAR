"""add persisted portfolio analytics snapshots

Revision ID: 6f7a8b9c0d1e
Revises: 5c6d7e8f9a0b
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "6f7a8b9c0d1e"
down_revision: Union[str, Sequence[str], None] = "5c6d7e8f9a0b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "portfolio_analytics_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("holding_count", sa.Integer(), nullable=False),
        sa.Column("valued_holding_count", sa.Integer(), nullable=False),
        sa.Column("total_cost_basis", sa.Numeric(12, 2), nullable=False),
        sa.Column("total_market_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("summary_metrics", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint("holding_count >= 0", name="holding_count_non_negative"),
        sa.CheckConstraint(
            "valued_holding_count >= 0", name="valued_holding_count_non_negative"
        ),
        sa.CheckConstraint(
            "total_cost_basis >= 0", name="total_cost_basis_non_negative"
        ),
        sa.CheckConstraint(
            "total_market_value >= 0", name="total_market_value_non_negative"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_portfolio_analytics_snapshots_user_generated_at",
        "portfolio_analytics_snapshots",
        ["user_id", "generated_at"],
    )
    op.create_table(
        "portfolio_holding_analytics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("analytics_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("portfolio_item_id", sa.Uuid(), nullable=True),
        sa.Column("set_number", sa.String(32), nullable=False),
        sa.Column("condition", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("cost_basis", sa.Numeric(12, 2), nullable=False),
        sa.Column("current_total_value", sa.Numeric(12, 2)),
        sa.Column("performance_percent", sa.Numeric(9, 2)),
        sa.Column("holding_days", sa.Integer()),
        sa.Column("valuation_confidence", sa.String(24), nullable=False),
        sa.Column("valuation_stale", sa.Boolean(), nullable=False),
        sa.Column("trend_label", sa.String(20), nullable=False),
        sa.Column("trend_percent", sa.Numeric(9, 2)),
        sa.Column("marketplace_supply", sa.Integer()),
        sa.Column("supply_reliable", sa.Boolean(), nullable=False),
        sa.Column("signal", sa.String(24), nullable=False),
        sa.Column("signal_score", sa.Integer(), nullable=False),
        sa.Column("flags", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="quantity_positive"),
        sa.CheckConstraint("cost_basis >= 0", name="cost_basis_non_negative"),
        sa.CheckConstraint(
            "current_total_value IS NULL OR current_total_value >= 0",
            name="current_total_value_non_negative",
        ),
        sa.CheckConstraint(
            "marketplace_supply IS NULL OR marketplace_supply >= 0",
            name="marketplace_supply_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["analytics_snapshot_id"],
            ["portfolio_analytics_snapshots.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["portfolio_item_id"], ["portfolio_items.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_portfolio_holding_analytics_snapshot_item",
        "portfolio_holding_analytics",
        ["analytics_snapshot_id", "portfolio_item_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_portfolio_holding_analytics_snapshot_item",
        table_name="portfolio_holding_analytics",
    )
    op.drop_table("portfolio_holding_analytics")
    op.drop_index(
        "ix_portfolio_analytics_snapshots_user_generated_at",
        table_name="portfolio_analytics_snapshots",
    )
    op.drop_table("portfolio_analytics_snapshots")
