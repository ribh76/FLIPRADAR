"""add completed portfolio analyses

Revision ID: 0b1c2d3e4f5a
Revises: 6f7a8b9c0d1e, 1a2b3c4d5e6f
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0b1c2d3e4f5a"
down_revision: Union[str, Sequence[str], None] = (
    "6f7a8b9c0d1e",
    "1a2b3c4d5e6f",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "portfolio_analyses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("analytics_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("prompt_version", sa.String(64), nullable=False),
        sa.Column("ai_narrative_status", sa.String(32), nullable=False),
        sa.Column("ai_narrative", sa.JSON()),
        sa.Column("item_recommendations", sa.JSON(), nullable=False),
        sa.Column("confidence_summary", sa.JSON(), nullable=False),
        sa.Column("data_quality_warnings", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["analytics_snapshot_id"],
            ["portfolio_analytics_snapshots.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_portfolio_analyses_user_generated_at",
        "portfolio_analyses",
        ["user_id", "generated_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_portfolio_analyses_user_generated_at", table_name="portfolio_analyses"
    )
    op.drop_table("portfolio_analyses")
