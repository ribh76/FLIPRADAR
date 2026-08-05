"""saved searches with versioned filters

Revision ID: aa1b2c3d4e5f
Revises: 5d1f8a2c7e3b
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "aa1b2c3d4e5f"
down_revision: Union[str, Sequence[str], None] = "5d1f8a2c7e3b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saved_searches",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("user_id", sa.Uuid(), nullable=False), sa.Column("name", sa.String(120), nullable=False),
        sa.Column("filter_config", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False), sa.Column("filter_version", sa.Integer(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True)), sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.CheckConstraint("filter_version >= 1", name="filter_version_valid"), sa.CheckConstraint("result_count >= 0", name="result_count_non_negative"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_saved_searches_user_updated", "saved_searches", ["user_id", "updated_at"])


def downgrade() -> None:
    op.drop_index("ix_saved_searches_user_updated", table_name="saved_searches")
    op.drop_table("saved_searches")
