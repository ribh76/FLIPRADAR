"""persist explainable per-listing evaluations

Revision ID: f9a2b3c4d5e6
Revises: e8f1a2b3c4d5
Create Date: 2026-08-06 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f9a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e8f1a2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "listing_evaluations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("listing_id", sa.Uuid(), nullable=False),
        sa.Column("fair_value", sa.Numeric(12, 2)),
        sa.Column("total_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("discount_percent", sa.Numeric(6, 2)),
        sa.Column("premium_percent", sa.Numeric(6, 2)),
        sa.Column("product_match_confidence", sa.Numeric(5, 2), nullable=False),
        sa.Column("decision", sa.String(24), nullable=False),
        sa.Column("decision_confidence", sa.Numeric(5, 2), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("risk_flags", sa.JSON(), nullable=False),
        sa.Column("score_breakdown", sa.JSON(), nullable=False),
        sa.Column(
            "valuation_sample_size", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("valuation_retrieved_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "decision IN ('buy', 'watch', 'pass', 'insufficient_data')",
            name="decision_allowed",
        ),
        sa.CheckConstraint(
            "decision_confidence BETWEEN 0 AND 100", name="decision_confidence_valid"
        ),
        sa.CheckConstraint("total_cost >= 0", name="total_cost_non_negative"),
        sa.ForeignKeyConstraint(
            ["listing_id"], ["marketplace_listings.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_listing_evaluations_listing_created",
        "listing_evaluations",
        ["listing_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_listing_evaluations_listing_created", table_name="listing_evaluations"
    )
    op.drop_table("listing_evaluations")
