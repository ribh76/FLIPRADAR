"""add user portfolios and migrate legacy holdings to defaults

Revision ID: c9d0e1f2a3b4
Revises: 7f8e9d0c1b2a
Create Date: 2026-08-13 00:00:00.000000
"""

from uuid import UUID, uuid4

import sqlalchemy as sa
from alembic import op

revision = "c9d0e1f2a3b4"
down_revision = "7f8e9d0c1b2a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portfolios",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("currency = upper(currency)", name="currency_uppercase"),
    )
    op.create_index("ix_portfolios_user_id", "portfolios", ["user_id"])
    op.create_index("ix_portfolios_user_created_at", "portfolios", ["user_id", "created_at"])

    bind = op.get_bind()
    users = bind.execute(sa.text("SELECT id FROM users")).mappings()
    defaults = [
        {
            "id": uuid4(),
            "user_id": UUID(str(row["id"])),
            "name": "Default Portfolio",
            "currency": "USD",
            "is_default": True,
        }
        for row in users
    ]
    if defaults:
        op.bulk_insert(
            sa.table(
                "portfolios",
                sa.column("id", sa.Uuid()), sa.column("user_id", sa.Uuid()),
                sa.column("name", sa.String()), sa.column("currency", sa.String()), sa.column("is_default", sa.Boolean()),
            ),
            defaults,
        )

    op.add_column("portfolio_items", sa.Column("portfolio_id", sa.Uuid(), nullable=True))
    for default in defaults:
        bind.execute(
            sa.text(
                "UPDATE portfolio_items SET portfolio_id = :portfolio_id "
                "WHERE user_id = :user_id"
            ).bindparams(
                sa.bindparam("portfolio_id", type_=sa.Uuid()),
                sa.bindparam("user_id", type_=sa.Uuid()),
            ),
            {"portfolio_id": default["id"], "user_id": default["user_id"]},
        )
    with op.batch_alter_table("portfolio_items") as batch_op:
        batch_op.alter_column("portfolio_id", nullable=False)
        batch_op.create_foreign_key("fk_portfolio_items_portfolio_id_portfolios", "portfolios", ["portfolio_id"], ["id"], ondelete="RESTRICT")
        batch_op.create_index("ix_portfolio_items_portfolio_id", ["portfolio_id"])


def downgrade() -> None:
    with op.batch_alter_table("portfolio_items") as batch_op:
        batch_op.drop_index("ix_portfolio_items_portfolio_id")
        batch_op.drop_constraint("fk_portfolio_items_portfolio_id_portfolios", type_="foreignkey")
        batch_op.drop_column("portfolio_id")
    op.drop_index("ix_portfolios_user_created_at", table_name="portfolios")
    op.drop_index("ix_portfolios_user_id", table_name="portfolios")
    op.drop_table("portfolios")
