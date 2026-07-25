"""account settings email change

Revision ID: d5a9b7c4e1f0
Revises: c3f2a1b9d8e7
Create Date: 2026-07-25 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5a9b7c4e1f0"
down_revision: Union[str, Sequence[str], None] = "c3f2a1b9d8e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("users", sa.Column("display_name", sa.String(length=120)))
    op.add_column("users", sa.Column("pending_email", sa.String(length=255)))
    op.execute("UPDATE users SET display_name = username WHERE display_name IS NULL")
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_users_pending_email"), ["pending_email"], unique=True
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_users_pending_email"))
    op.drop_column("users", "pending_email")
    op.drop_column("users", "display_name")
