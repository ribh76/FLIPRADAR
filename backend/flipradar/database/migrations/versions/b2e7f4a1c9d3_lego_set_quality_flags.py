"""add LEGO set quality and completeness flags

Revision ID: b2e7f4a1c9d3
Revises: 9a3d8f2b6c1e
Create Date: 2026-07-27 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2e7f4a1c9d3"
down_revision: Union[str, Sequence[str], None] = "9a3d8f2b6c1e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
    if _is_sqlite():
        with op.batch_alter_table("lego_sets", recreate="always") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "data_quality_flag",
                    sa.Boolean(),
                    server_default=sa.text("false"),
                    nullable=False,
                )
            )
            batch_op.add_column(
                sa.Column(
                    "completeness_flag",
                    sa.Boolean(),
                    server_default=sa.text("false"),
                    nullable=False,
                )
            )
            batch_op.create_check_constraint(
                batch_op.f("ck_lego_sets_completeness_flag_requirements"),
                "completeness_flag = false OR (theme IS NOT NULL AND release_year IS NOT NULL AND piece_count IS NOT NULL)",
            )
        return

    op.add_column(
        "lego_sets",
        sa.Column(
            "data_quality_flag",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "lego_sets",
        sa.Column(
            "completeness_flag",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        op.f("ck_lego_sets_completeness_flag_requirements"),
        "lego_sets",
        "completeness_flag = false OR (theme IS NOT NULL AND release_year IS NOT NULL AND piece_count IS NOT NULL)",
    )


def downgrade() -> None:
    if _is_sqlite():
        with op.batch_alter_table("lego_sets", recreate="always") as batch_op:
            batch_op.drop_constraint(
                batch_op.f("ck_lego_sets_completeness_flag_requirements"),
                type_="check",
            )
            batch_op.drop_column("completeness_flag")
            batch_op.drop_column("data_quality_flag")
        return

    op.drop_constraint(
        op.f("ck_lego_sets_completeness_flag_requirements"),
        "lego_sets",
        type_="check",
    )
    op.drop_column("lego_sets", "completeness_flag")
    op.drop_column("lego_sets", "data_quality_flag")
