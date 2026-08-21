"""add price snapshot timestamp defaults

Revision ID: f3d4e5a6b7c8
Revises: f2c3d4e5a6b7
Create Date: 2026-08-21 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op


revision = "f3d4e5a6b7c8"
down_revision = "f2c3d4e5a6b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for column_name in ("retrieval_time", "created_at", "updated_at"):
        op.alter_column(
            "price_snapshots",
            column_name,
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
            server_default=sa.text("now()"),
        )


def downgrade() -> None:
    for column_name in ("updated_at", "created_at", "retrieval_time"):
        op.alter_column(
            "price_snapshots",
            column_name,
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
            server_default=None,
        )
