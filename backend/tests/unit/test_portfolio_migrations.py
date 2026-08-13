"""Regression coverage for the legacy-holding portfolio migration."""

from importlib import import_module
from uuid import uuid4

import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext


def test_multi_portfolio_migration_creates_defaults_and_backfills_holdings():
    """Existing users retain every holding after the portfolio_id becomes required."""
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    users = sa.Table("users", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    items = sa.Table(
        "portfolio_items",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
    )
    metadata.create_all(engine)
    first_user, second_user = uuid4(), uuid4()
    with engine.begin() as connection:
        connection.execute(users.insert(), [{"id": first_user}, {"id": second_user}])
        connection.execute(
            items.insert(),
            [{"id": uuid4(), "user_id": first_user}, {"id": uuid4(), "user_id": first_user}, {"id": uuid4(), "user_id": second_user}],
        )
        context = MigrationContext.configure(connection)
        migration = import_module(
            "flipradar.database.migrations.versions.c9d0e1f2a3b4_multi_portfolios"
        )
        original_op = migration.op
        migration.op = Operations(context)
        try:
            migration.upgrade()
        finally:
            migration.op = original_op

        portfolios = connection.execute(
            sa.text("SELECT user_id, name, is_default FROM portfolios ORDER BY user_id")
        ).mappings().all()
        holding_portfolios = connection.execute(
            sa.text("SELECT portfolio_id FROM portfolio_items")
        ).scalars().all()

    assert len(portfolios) == 2
    assert {row["name"] for row in portfolios} == {"Default Portfolio"}
    assert all(row["is_default"] for row in portfolios)
    assert len(holding_portfolios) == 3
    assert all(holding_portfolios)


def test_scoped_analytics_migration_is_chained_after_portfolio_backfill():
    migration = import_module(
        "flipradar.database.migrations.versions.d0e1f2a3b4c5_portfolio_archiving_and_scoping"
    )

    assert migration.down_revision == "c9d0e1f2a3b4"
