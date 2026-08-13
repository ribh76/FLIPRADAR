"""Add durable audit records for completed portfolio CSV imports.

Revision ID: af1b2c3d4e5f
Revises: 0f3a9b7d2c6e
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "af1b2c3d4e5f"
down_revision: Union[str, Sequence[str], None] = "0f3a9b7d2c6e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "portfolio_import_audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("portfolio_id", sa.Uuid(), nullable=False),
        sa.Column("source_rows", sa.Integer(), nullable=False),
        sa.Column("items_created", sa.Integer(), nullable=False),
        sa.Column("merged_rows", sa.Integer(), nullable=False),
        sa.Column("duplicate_handling", sa.String(length=20), nullable=False),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("source_rows > 0", name="source_rows_positive"),
        sa.CheckConstraint("items_created >= 0", name="items_created_non_negative"),
        sa.CheckConstraint("merged_rows >= 0", name="merged_rows_non_negative"),
        sa.ForeignKeyConstraint(
            ["portfolio_id"], ["portfolios.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_portfolio_import_audit_user_created",
        "portfolio_import_audit_logs",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_portfolio_import_audit_user_created",
        table_name="portfolio_import_audit_logs",
    )
    op.drop_table("portfolio_import_audit_logs")
