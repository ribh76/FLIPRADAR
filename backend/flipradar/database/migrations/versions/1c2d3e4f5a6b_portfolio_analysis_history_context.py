"""store portfolio analysis method versions and context

Revision ID: 1c2d3e4f5a6b
Revises: 0b1c2d3e4f5a
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "1c2d3e4f5a6b"
down_revision: Union[str, Sequence[str], None] = "0b1c2d3e4f5a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "portfolio_analyses",
        sa.Column(
            "method_version",
            sa.String(64),
            nullable=False,
            server_default="portfolio-analysis-method-v1",
        ),
    )
    op.add_column(
        "portfolio_analyses",
        sa.Column(
            "portfolio_context",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("portfolio_analyses", "portfolio_context")
    op.drop_column("portfolio_analyses", "method_version")
