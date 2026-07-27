"""add LEGO set catalog metadata

Revision ID: 9a3d8f2b6c1e
Revises: f7c1d2e3a4b5
Create Date: 2026-07-27 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "9a3d8f2b6c1e"
down_revision: Union[str, Sequence[str], None] = "f7c1d2e3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
    """Add catalog fields while preserving existing LEGO set records."""
    if _is_sqlite():
        with op.batch_alter_table(
            "lego_sets", schema=None, recreate="always"
        ) as batch_op:
            batch_op.add_column(sa.Column("msrp", sa.Numeric(12, 2), nullable=True))
            batch_op.add_column(
                sa.Column("original_currency", sa.String(3), nullable=True)
            )
            batch_op.add_column(sa.Column("region", sa.String(16), nullable=True))
            batch_op.add_column(sa.Column("image_urls", sa.JSON(), nullable=True))
            batch_op.add_column(sa.Column("source_name", sa.String(120), nullable=True))
            batch_op.add_column(sa.Column("source_url", sa.String(1000), nullable=True))
            batch_op.create_check_constraint(
                batch_op.f("ck_lego_sets_msrp_non_negative"),
                "msrp IS NULL OR msrp >= 0",
            )
            batch_op.create_check_constraint(
                batch_op.f("ck_lego_sets_original_currency_uppercase"),
                "original_currency IS NULL OR original_currency = upper(original_currency)",
            )
            batch_op.create_check_constraint(
                batch_op.f("ck_lego_sets_region_uppercase"),
                "region IS NULL OR region = upper(region)",
            )
        return

    op.add_column("lego_sets", sa.Column("msrp", sa.Numeric(12, 2), nullable=True))
    op.add_column(
        "lego_sets", sa.Column("original_currency", sa.String(3), nullable=True)
    )
    op.add_column("lego_sets", sa.Column("region", sa.String(16), nullable=True))
    op.add_column(
        "lego_sets",
        sa.Column(
            "image_urls",
            sa.JSON().with_variant(
                postgresql.JSONB(astext_type=sa.Text()), "postgresql"
            ),
            nullable=True,
        ),
    )
    op.add_column("lego_sets", sa.Column("source_name", sa.String(120), nullable=True))
    op.add_column("lego_sets", sa.Column("source_url", sa.String(1000), nullable=True))
    op.create_check_constraint(
        op.f("ck_lego_sets_msrp_non_negative"),
        "lego_sets",
        "msrp IS NULL OR msrp >= 0",
    )
    op.create_check_constraint(
        op.f("ck_lego_sets_original_currency_uppercase"),
        "lego_sets",
        "original_currency IS NULL OR original_currency = upper(original_currency)",
    )
    op.create_check_constraint(
        op.f("ck_lego_sets_region_uppercase"),
        "lego_sets",
        "region IS NULL OR region = upper(region)",
    )


def downgrade() -> None:
    """Remove catalog fields added by this revision."""
    if _is_sqlite():
        with op.batch_alter_table(
            "lego_sets", schema=None, recreate="always"
        ) as batch_op:
            batch_op.drop_constraint(
                batch_op.f("ck_lego_sets_region_uppercase"), type_="check"
            )
            batch_op.drop_constraint(
                batch_op.f("ck_lego_sets_original_currency_uppercase"),
                type_="check",
            )
            batch_op.drop_constraint(
                batch_op.f("ck_lego_sets_msrp_non_negative"), type_="check"
            )
            batch_op.drop_column("source_url")
            batch_op.drop_column("source_name")
            batch_op.drop_column("image_urls")
            batch_op.drop_column("region")
            batch_op.drop_column("original_currency")
            batch_op.drop_column("msrp")
        return

    op.drop_constraint(
        op.f("ck_lego_sets_region_uppercase"), "lego_sets", type_="check"
    )
    op.drop_constraint(
        op.f("ck_lego_sets_original_currency_uppercase"),
        "lego_sets",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_lego_sets_msrp_non_negative"), "lego_sets", type_="check"
    )
    op.drop_column("lego_sets", "source_url")
    op.drop_column("lego_sets", "source_name")
    op.drop_column("lego_sets", "image_urls")
    op.drop_column("lego_sets", "region")
    op.drop_column("lego_sets", "original_currency")
    op.drop_column("lego_sets", "msrp")
