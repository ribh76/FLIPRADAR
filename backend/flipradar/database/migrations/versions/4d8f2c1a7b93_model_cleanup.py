"""model cleanup

Revision ID: 4d8f2c1a7b93
Revises: 944a49cd533d
Create Date: 2026-07-23 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4d8f2c1a7b93"
down_revision: Union[str, Sequence[str], None] = "944a49cd533d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamp_column(name: str) -> sa.Column:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        server_default=sa.text("(CURRENT_TIMESTAMP)"),
        nullable=False,
    )


def _is_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def _drop_constraint_if_exists(table_name: str, constraint_name: str) -> None:
    op.execute(
        sa.text(
            f'ALTER TABLE "{table_name}" DROP CONSTRAINT IF EXISTS "{constraint_name}"'
        )
    )


def _upgrade_portfolio_items() -> None:
    if _is_sqlite():
        with op.batch_alter_table(
            "portfolio_items", schema=None, recreate="always"
        ) as batch_op:
            batch_op.drop_index("ix_portfolio_items_set_number")
            batch_op.drop_index("ix_portfolio_items_user_set")
            batch_op.drop_constraint(
                op.f("fk_portfolio_items_set_number_lego_sets"), type_="foreignkey"
            )
            batch_op.drop_constraint(
                op.f("ck_portfolio_items_set_number_canonical"), type_="check"
            )
            batch_op.add_column(sa.Column("lego_set_id", sa.Uuid(), nullable=False))
            batch_op.drop_column("set_number")
            batch_op.create_foreign_key(
                batch_op.f("fk_portfolio_items_lego_set_id_lego_sets"),
                "lego_sets",
                ["lego_set_id"],
                ["id"],
                ondelete="RESTRICT",
            )
            batch_op.create_index(
                "ix_portfolio_items_lego_set_id", ["lego_set_id"], unique=False
            )
            batch_op.create_index(
                "ix_portfolio_items_user_lego_set",
                ["user_id", "lego_set_id"],
                unique=False,
            )
            batch_op.create_index(
                "ix_portfolio_items_user_created_at",
                ["user_id", "created_at"],
                unique=False,
            )
        return

    op.add_column("portfolio_items", sa.Column("lego_set_id", sa.Uuid(), nullable=True))
    op.execute("""
        UPDATE portfolio_items AS portfolio_item
        SET lego_set_id = lego_set.id
        FROM lego_sets AS lego_set
        WHERE portfolio_item.set_number = lego_set.set_number
        """)
    op.alter_column("portfolio_items", "lego_set_id", nullable=False)
    op.drop_index("ix_portfolio_items_set_number", table_name="portfolio_items")
    op.drop_index("ix_portfolio_items_user_set", table_name="portfolio_items")
    _drop_constraint_if_exists(
        "portfolio_items", "fk_portfolio_items_set_number_lego_sets"
    )
    _drop_constraint_if_exists(
        "portfolio_items", "ck_portfolio_items_set_number_canonical"
    )
    op.drop_column("portfolio_items", "set_number")
    op.create_foreign_key(
        op.f("fk_portfolio_items_lego_set_id_lego_sets"),
        "portfolio_items",
        "lego_sets",
        ["lego_set_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_portfolio_items_lego_set_id",
        "portfolio_items",
        ["lego_set_id"],
        unique=False,
    )
    op.create_index(
        "ix_portfolio_items_user_lego_set",
        "portfolio_items",
        ["user_id", "lego_set_id"],
        unique=False,
    )
    op.create_index(
        "ix_portfolio_items_user_created_at",
        "portfolio_items",
        ["user_id", "created_at"],
        unique=False,
    )


def _downgrade_portfolio_items() -> None:
    if _is_sqlite():
        with op.batch_alter_table(
            "portfolio_items", schema=None, recreate="always"
        ) as batch_op:
            batch_op.drop_index("ix_portfolio_items_user_created_at")
            batch_op.drop_index("ix_portfolio_items_user_lego_set")
            batch_op.drop_index("ix_portfolio_items_lego_set_id")
            batch_op.drop_constraint(
                op.f("fk_portfolio_items_lego_set_id_lego_sets"), type_="foreignkey"
            )
            batch_op.add_column(sa.Column("set_number", sa.String(32), nullable=False))
            batch_op.drop_column("lego_set_id")
            batch_op.create_check_constraint(
                batch_op.f("ck_portfolio_items_set_number_canonical"),
                "set_number = upper(trim(set_number))",
            )
            batch_op.create_foreign_key(
                batch_op.f("fk_portfolio_items_set_number_lego_sets"),
                "lego_sets",
                ["set_number"],
                ["set_number"],
                ondelete="RESTRICT",
            )
            batch_op.create_index(
                "ix_portfolio_items_set_number", ["set_number"], unique=False
            )
            batch_op.create_index(
                "ix_portfolio_items_user_set",
                ["user_id", "set_number"],
                unique=False,
            )
        return

    op.add_column(
        "portfolio_items", sa.Column("set_number", sa.String(32), nullable=True)
    )
    op.execute("""
        UPDATE portfolio_items AS portfolio_item
        SET set_number = lego_set.set_number
        FROM lego_sets AS lego_set
        WHERE portfolio_item.lego_set_id = lego_set.id
        """)
    op.alter_column("portfolio_items", "set_number", nullable=False)
    op.drop_index("ix_portfolio_items_user_created_at", table_name="portfolio_items")
    op.drop_index("ix_portfolio_items_user_lego_set", table_name="portfolio_items")
    op.drop_index("ix_portfolio_items_lego_set_id", table_name="portfolio_items")
    _drop_constraint_if_exists(
        "portfolio_items", "fk_portfolio_items_lego_set_id_lego_sets"
    )
    op.drop_column("portfolio_items", "lego_set_id")
    op.create_check_constraint(
        op.f("ck_portfolio_items_set_number_canonical"),
        "portfolio_items",
        "set_number = upper(trim(set_number))",
    )
    op.create_foreign_key(
        op.f("fk_portfolio_items_set_number_lego_sets"),
        "portfolio_items",
        "lego_sets",
        ["set_number"],
        ["set_number"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_portfolio_items_set_number",
        "portfolio_items",
        ["set_number"],
        unique=False,
    )
    op.create_index(
        "ix_portfolio_items_user_set",
        "portfolio_items",
        ["user_id", "set_number"],
        unique=False,
    )


def _add_timestamp_columns() -> None:
    if _is_sqlite():
        with op.batch_alter_table(
            "price_snapshots", schema=None, recreate="always"
        ) as batch_op:
            batch_op.add_column(_timestamp_column("updated_at"))
        with op.batch_alter_table(
            "recommendations", schema=None, recreate="always"
        ) as batch_op:
            batch_op.add_column(_timestamp_column("updated_at"))
        return

    op.add_column("price_snapshots", _timestamp_column("updated_at"))
    op.add_column("recommendations", _timestamp_column("updated_at"))


def _drop_timestamp_columns() -> None:
    if _is_sqlite():
        with op.batch_alter_table(
            "recommendations", schema=None, recreate="always"
        ) as batch_op:
            batch_op.drop_column("updated_at")
        with op.batch_alter_table(
            "price_snapshots", schema=None, recreate="always"
        ) as batch_op:
            batch_op.drop_column("updated_at")
        return

    op.drop_column("recommendations", "updated_at")
    op.drop_column("price_snapshots", "updated_at")


def upgrade() -> None:
    """Upgrade schema."""
    _upgrade_portfolio_items()
    _add_timestamp_columns()
    op.create_index(
        "ix_price_snapshots_set_condition_snapshot_at",
        "price_snapshots",
        ["lego_set_id", "condition", "snapshot_at"],
        unique=False,
    )
    op.create_index(
        "ix_price_snapshots_marketplace_condition_snapshot_at",
        "price_snapshots",
        ["marketplace_id", "condition", "snapshot_at"],
        unique=False,
    )
    op.create_index(
        "ix_recommendations_set_decision_created_at",
        "recommendations",
        ["lego_set_id", "decision", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_recommendations_set_decision_created_at", table_name="recommendations"
    )
    op.drop_index(
        "ix_price_snapshots_marketplace_condition_snapshot_at",
        table_name="price_snapshots",
    )
    op.drop_index(
        "ix_price_snapshots_set_condition_snapshot_at", table_name="price_snapshots"
    )
    _drop_timestamp_columns()
    _downgrade_portfolio_items()
