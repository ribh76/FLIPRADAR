"""add part catalog tables

Revision ID: 8c1d2e3f4a5b
Revises: 2d3e4f5a6b7c
Create Date: 2026-08-12 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "8c1d2e3f4a5b"
down_revision: Union[str, Sequence[str], None] = "2d3e4f5a6b7c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _json_document() -> sa.JSON:
    return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def _catalog_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_identifiers", _json_document(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("aliases", _json_document(), nullable=False),
        sa.Column("mold_variants", _json_document(), nullable=False),
        sa.Column("image_urls", _json_document(), nullable=False),
        sa.Column("first_known_year", sa.Integer(), nullable=True),
        sa.Column("last_known_year", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
    ]


def _catalog_constraints() -> list[sa.CheckConstraint]:
    return [
        sa.CheckConstraint(
            "first_known_year IS NULL OR first_known_year BETWEEN 1949 AND 2100",
            name="first_known_year_valid",
        ),
        sa.CheckConstraint(
            "last_known_year IS NULL OR last_known_year BETWEEN 1949 AND 2100",
            name="last_known_year_valid",
        ),
        sa.CheckConstraint(
            "last_known_year IS NULL OR first_known_year IS NULL OR last_known_year >= first_known_year",
            name="known_year_range_valid",
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "part_categories",
        *_catalog_columns(),
        *_catalog_constraints(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "colors",
        *_catalog_columns(),
        *_catalog_constraints(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "parts",
        *_catalog_columns(),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        *_catalog_constraints(),
        sa.ForeignKeyConstraint(
            ["category_id"], ["part_categories.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_parts_category_id", "parts", ["category_id"])
    op.create_index("ix_parts_category_id_name", "parts", ["category_id", "name"])

    op.create_table(
        "elements",
        *_catalog_columns(),
        sa.Column("part_id", sa.Uuid(), nullable=False),
        sa.Column("color_id", sa.Uuid(), nullable=False),
        *_catalog_constraints(),
        sa.ForeignKeyConstraint(["part_id"], ["parts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["color_id"], ["colors.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_elements_part_id", "elements", ["part_id"])
    op.create_index("ix_elements_color_id", "elements", ["color_id"])
    op.create_index("ix_elements_part_id_color_id", "elements", ["part_id", "color_id"])


def downgrade() -> None:
    op.drop_index("ix_elements_part_id_color_id", table_name="elements")
    op.drop_index("ix_elements_color_id", table_name="elements")
    op.drop_index("ix_elements_part_id", table_name="elements")
    op.drop_table("elements")
    op.drop_index("ix_parts_category_id_name", table_name="parts")
    op.drop_index("ix_parts_category_id", table_name="parts")
    op.drop_table("parts")
    op.drop_table("colors")
    op.drop_table("part_categories")
