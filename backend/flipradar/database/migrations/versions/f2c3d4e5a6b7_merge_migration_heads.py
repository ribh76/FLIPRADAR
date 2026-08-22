"""merge migration heads

Revision ID: f2c3d4e5a6b7
Revises: 5b7d9e2f4a6c, af1b2c3d4e5f
Create Date: 2026-08-21 00:00:00.000000
"""

from typing import Sequence, Union

revision: str = "f2c3d4e5a6b7"
down_revision: Union[str, Sequence[str], None] = (
    "5b7d9e2f4a6c",
    "af1b2c3d4e5f",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Unify independently developed migration branches."""


def downgrade() -> None:
    """Split the migration graph back into its parent branches."""
