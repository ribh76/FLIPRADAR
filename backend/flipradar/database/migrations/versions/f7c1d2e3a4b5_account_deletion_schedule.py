"""account deletion schedule

Revision ID: f7c1d2e3a4b5
Revises: e6b2c8d9f4a1
Create Date: 2026-07-25 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7c1d2e3a4b5"
down_revision: Union[str, Sequence[str], None] = "e6b2c8d9f4a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users", sa.Column("deletion_requested_at", sa.DateTime(timezone=True))
    )
    op.add_column(
        "users", sa.Column("deletion_scheduled_at", sa.DateTime(timezone=True))
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "deletion_scheduled_at")
    op.drop_column("users", "deletion_requested_at")
