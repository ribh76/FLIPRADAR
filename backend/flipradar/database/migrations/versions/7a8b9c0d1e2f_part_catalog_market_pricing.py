"""add optional part catalog market pricing

Revision ID: 7a8b9c0d1e2f
Revises: 4f5a6b7c8d9e
Create Date: 2026-08-12 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "7a8b9c0d1e2f"
down_revision: Union[str, Sequence[str], None] = "4f5a6b7c8d9e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("parts") as batch_op:
        batch_op.add_column(sa.Column("market_price", sa.Numeric(12, 2)))
        batch_op.add_column(sa.Column("market_price_currency", sa.String(length=3)))


def downgrade() -> None:
    with op.batch_alter_table("parts") as batch_op:
        batch_op.drop_column("market_price_currency")
        batch_op.drop_column("market_price")
