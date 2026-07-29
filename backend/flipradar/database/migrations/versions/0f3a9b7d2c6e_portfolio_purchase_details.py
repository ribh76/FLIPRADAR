"""add purchase date and currency to portfolio items

Revision ID: 0f3a9b7d2c6e
Revises: f7c1d2e3a4b5
Create Date: 2026-07-29 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0f3a9b7d2c6e"
down_revision: Union[str, Sequence[str], None] = ("f7c1d2e3a4b5", "a9e4c1b7d2f8")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Preserve existing dates and give legacy purchases a USD currency."""
    with op.batch_alter_table("portfolio_items", schema=None) as batch_op:
        batch_op.alter_column("acquired_at", new_column_name="purchase_date")
        batch_op.add_column(
            sa.Column(
                "currency", sa.String(length=3), nullable=False, server_default="USD"
            )
        )
        batch_op.create_check_constraint(
            "currency_uppercase", "currency = upper(currency)"
        )


def downgrade() -> None:
    with op.batch_alter_table("portfolio_items", schema=None) as batch_op:
        batch_op.drop_constraint("currency_uppercase", type_="check")
        batch_op.drop_column("currency")
        batch_op.alter_column("purchase_date", new_column_name="acquired_at")
