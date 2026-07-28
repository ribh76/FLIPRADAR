"""persist marketplace listing match explanations

Revision ID: d1e2f3a4b5c6
Revises: c6e4a1d8f2b7
Create Date: 2026-07-28 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "c6e4a1d8f2b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Store match reason and exclusion-flag arrays alongside each listing."""
    op.add_column(
        "marketplace_listings", sa.Column("match_reasons", sa.JSON(), nullable=True)
    )
    op.add_column(
        "marketplace_listings", sa.Column("exclusion_flags", sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    """Remove persisted matching explanations."""
    op.drop_column("marketplace_listings", "exclusion_flags")
    op.drop_column("marketplace_listings", "match_reasons")
