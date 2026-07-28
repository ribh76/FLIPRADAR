"""add detected set number to marketplace listings

Revision ID: c6e4a1d8f2b7
Revises: b2e7f4a1c9d3
Create Date: 2026-07-27 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c6e4a1d8f2b7"
down_revision: Union[str, Sequence[str], None] = "b2e7f4a1c9d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
    """Persist the catalog number detected from raw marketplace listing data."""
    if _is_sqlite():
        with op.batch_alter_table(
            "marketplace_listings", schema=None, recreate="always"
        ) as batch_op:
            batch_op.add_column(
                sa.Column("detected_set_number", sa.String(length=32), nullable=True)
            )
            batch_op.create_check_constraint(
                batch_op.f("ck_marketplace_listings_detected_set_number_canonical"),
                "detected_set_number IS NULL OR detected_set_number = upper(trim(detected_set_number))",
            )
        return

    op.add_column(
        "marketplace_listings",
        sa.Column("detected_set_number", sa.String(length=32), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_marketplace_listings_detected_set_number_canonical"),
        "marketplace_listings",
        "detected_set_number IS NULL OR detected_set_number = upper(trim(detected_set_number))",
    )


def downgrade() -> None:
    """Remove the raw detected set number field."""
    if _is_sqlite():
        with op.batch_alter_table(
            "marketplace_listings", schema=None, recreate="always"
        ) as batch_op:
            batch_op.drop_constraint(
                batch_op.f("ck_marketplace_listings_detected_set_number_canonical"),
                type_="check",
            )
            batch_op.drop_column("detected_set_number")
        return

    op.drop_constraint(
        op.f("ck_marketplace_listings_detected_set_number_canonical"),
        "marketplace_listings",
        type_="check",
    )
    op.drop_column("marketplace_listings", "detected_set_number")
