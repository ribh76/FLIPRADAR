"""store whether listing data came from a verified provider

Revision ID: e8f1a2b3c4d5
Revises: aa1b2c3d4e5f
Create Date: 2026-08-06 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e8f1a2b3c4d5"
down_revision: Union[str, Sequence[str], None] = "aa1b2c3d4e5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "marketplace_listings",
        sa.Column(
            "is_verified", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
    )
    op.alter_column("marketplace_listings", "is_verified", server_default=None)


def downgrade() -> None:
    op.drop_column("marketplace_listings", "is_verified")
