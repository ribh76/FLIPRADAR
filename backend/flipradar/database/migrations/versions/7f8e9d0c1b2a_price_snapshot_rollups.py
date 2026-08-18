"""add compact weekly and monthly price history rollups

Revision ID: 7f8e9d0c1b2a
Revises: 0e3f5a7b9c1d
Create Date: 2026-08-12 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "7f8e9d0c1b2a"
down_revision: Union[str, Sequence[str], None] = "0e3f5a7b9c1d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "price_snapshot_rollups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lego_set_id", sa.Uuid(), nullable=False),
        sa.Column("marketplace_id", sa.Uuid(), nullable=False),
        sa.Column("condition", sa.String(20), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("metric_type", sa.String(30), nullable=False),
        sa.Column("period", sa.String(10), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("average_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("low_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("high_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("latest_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("average_sample_size", sa.Integer(), nullable=False),
        sa.Column("observation_count", sa.Integer(), nullable=False),
        sa.Column("latest_retrieval_time", sa.DateTime(timezone=True), nullable=False),
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
        sa.CheckConstraint("period IN ('weekly', 'monthly')", name="period_allowed"),
        sa.CheckConstraint("observation_count > 0", name="observation_count_positive"),
        sa.CheckConstraint("average_value >= 0", name="average_value_non_negative"),
        sa.CheckConstraint("low_value >= 0", name="low_value_non_negative"),
        sa.CheckConstraint("high_value >= low_value", name="value_range_ordered"),
        sa.ForeignKeyConstraint(["lego_set_id"], ["lego_sets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["marketplace_id"], ["marketplaces.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "lego_set_id",
            "marketplace_id",
            "condition",
            "currency",
            "metric_type",
            "period",
            "period_start",
            name="uq_price_snapshot_rollups_period",
        ),
    )
    op.create_index(
        "ix_price_snapshot_rollups_set_period_start",
        "price_snapshot_rollups",
        ["lego_set_id", "period", "period_start"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_price_snapshot_rollups_set_period_start",
        table_name="price_snapshot_rollups",
    )
    op.drop_table("price_snapshot_rollups")
