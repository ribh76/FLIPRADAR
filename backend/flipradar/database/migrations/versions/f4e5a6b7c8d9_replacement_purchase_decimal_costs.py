"""store replacement purchase costs as exact decimals

Revision ID: f4e5a6b7c8d9
Revises: f3d4e5a6b7c8
Create Date: 2026-08-21 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "f4e5a6b7c8d9"
down_revision = "f3d4e5a6b7c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "replacement_purchase_items",
        "estimated_unit_cost",
        existing_type=sa.Float(),
        existing_nullable=False,
        existing_server_default=sa.text("0"),
        type_=sa.Numeric(precision=12, scale=2),
        server_default=sa.text("0.00"),
        postgresql_using="estimated_unit_cost::numeric(12, 2)",
    )
    op.alter_column(
        "replacement_purchase_items",
        "actual_unit_cost",
        existing_type=sa.Float(),
        existing_nullable=True,
        type_=sa.Numeric(precision=12, scale=2),
        postgresql_using="actual_unit_cost::numeric(12, 2)",
    )


def downgrade() -> None:
    op.alter_column(
        "replacement_purchase_items",
        "actual_unit_cost",
        existing_type=sa.Numeric(precision=12, scale=2),
        existing_nullable=True,
        type_=sa.Float(),
        postgresql_using="actual_unit_cost::double precision",
    )
    op.alter_column(
        "replacement_purchase_items",
        "estimated_unit_cost",
        existing_type=sa.Numeric(precision=12, scale=2),
        existing_nullable=False,
        existing_server_default=sa.text("0.00"),
        type_=sa.Float(),
        server_default=sa.text("0"),
        postgresql_using="estimated_unit_cost::double precision",
    )
