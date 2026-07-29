"""add portfolio valuation daily rollups

Revision ID: 5d1f8a2c7e3b
Revises: 7e2a4c9b1d6f
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "5d1f8a2c7e3b"
down_revision: Union[str, Sequence[str], None] = "7e2a4c9b1d6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "portfolio_valuation_daily_rollups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("rollup_date", sa.Date(), nullable=False),
        sa.Column("cost_basis", sa.Numeric(12, 2), nullable=False),
        sa.Column("market_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("gain_loss", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
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
            "rollup_date",
            name="uq_portfolio_valuation_daily_rollups_user_date",
        ),
    )
    op.create_index(
        "ix_portfolio_valuation_daily_rollups_user_date",
        "portfolio_valuation_daily_rollups",
        ["user_id", "rollup_date"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_portfolio_valuation_daily_rollups_user_date",
        table_name="portfolio_valuation_daily_rollups",
    )
    op.drop_table("portfolio_valuation_daily_rollups")
