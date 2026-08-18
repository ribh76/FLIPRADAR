"""add portfolio archiving and scoped analytics

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-08-13 00:10:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("portfolios", sa.Column("archived_at", sa.DateTime(timezone=True)))
    op.add_column("portfolio_analytics_snapshots", sa.Column("portfolio_id", sa.Uuid()))
    op.create_foreign_key(
        "fk_portfolio_analytics_snapshots_portfolio_id_portfolios",
        "portfolio_analytics_snapshots",
        "portfolios",
        ["portfolio_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_portfolio_analytics_snapshots_portfolio_generated_at",
        "portfolio_analytics_snapshots",
        ["portfolio_id", "generated_at"],
    )
    op.add_column("portfolio_analyses", sa.Column("portfolio_id", sa.Uuid()))
    op.create_foreign_key(
        "fk_portfolio_analyses_portfolio_id_portfolios",
        "portfolio_analyses",
        "portfolios",
        ["portfolio_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_portfolio_analyses_portfolio_id_portfolios",
        "portfolio_analyses",
        type_="foreignkey",
    )
    op.drop_column("portfolio_analyses", "portfolio_id")
    op.drop_index(
        "ix_portfolio_analytics_snapshots_portfolio_generated_at",
        table_name="portfolio_analytics_snapshots",
    )
    op.drop_constraint(
        "fk_portfolio_analytics_snapshots_portfolio_id_portfolios",
        "portfolio_analytics_snapshots",
        type_="foreignkey",
    )
    op.drop_column("portfolio_analytics_snapshots", "portfolio_id")
    op.drop_column("portfolios", "archived_at")
