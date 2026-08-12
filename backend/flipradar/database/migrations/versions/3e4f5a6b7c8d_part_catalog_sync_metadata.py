"""add part catalog synchronization metadata

Revision ID: 3e4f5a6b7c8d
Revises: 8c1d2e3f4a5b
Create Date: 2026-08-12 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "3e4f5a6b7c8d"
down_revision: Union[str, Sequence[str], None] = "8c1d2e3f4a5b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ("part_categories", "colors", "parts", "elements")


def upgrade() -> None:
    for table in _TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(
                sa.Column("canonical_identifier", sa.String(length=160), nullable=True)
            )
            batch_op.add_column(sa.Column("source_name", sa.String(length=120)))
            batch_op.add_column(sa.Column("source_url", sa.String(length=1000)))
            batch_op.add_column(
                sa.Column("source_updated_at", sa.DateTime(timezone=True))
            )
            batch_op.add_column(sa.Column("fetched_at", sa.DateTime(timezone=True)))

        op.execute(
            sa.text(
                f"UPDATE {table} SET canonical_identifier = 'legacy:' || id "
                "WHERE canonical_identifier IS NULL"
            )
        )
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column("canonical_identifier", nullable=False)
            batch_op.create_unique_constraint(
                f"uq_{table}_canonical_identifier", ["canonical_identifier"]
            )
            batch_op.create_index(
                f"ix_{table}_canonical_identifier", ["canonical_identifier"]
            )
            batch_op.create_index(f"ix_{table}_name", ["name"])


def downgrade() -> None:
    for table in reversed(_TABLES):
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_index(f"ix_{table}_name")
            batch_op.drop_index(f"ix_{table}_canonical_identifier")
            batch_op.drop_constraint(f"uq_{table}_canonical_identifier", type_="unique")
            batch_op.drop_column("fetched_at")
            batch_op.drop_column("source_updated_at")
            batch_op.drop_column("source_url")
            batch_op.drop_column("source_name")
            batch_op.drop_column("canonical_identifier")
