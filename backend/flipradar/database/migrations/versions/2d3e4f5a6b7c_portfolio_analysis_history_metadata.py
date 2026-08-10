"""add portfolio analysis history metadata

Revision ID: 2d3e4f5a6b7c
Revises: 1c2d3e4f5a6b
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "2d3e4f5a6b7c"
down_revision: Union[str, Sequence[str], None] = "1c2d3e4f5a6b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "portfolio_analyses",
        sa.Column("labels", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column("portfolio_analyses", sa.Column("annotation", sa.String(1000)))
    op.add_column(
        "portfolio_analyses",
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_column("portfolio_analyses", "deleted_at")
    op.drop_column("portfolio_analyses", "annotation")
    op.drop_column("portfolio_analyses", "labels")
