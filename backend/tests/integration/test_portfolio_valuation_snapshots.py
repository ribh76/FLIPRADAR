from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import flipradar.domain.models  # noqa: F401
from flipradar.api.schemas import PortfolioItemCreate
from flipradar.database import Base
from flipradar.domain.models import (
    LegoSet,
    PortfolioItemValuationSnapshot,
    PortfolioValuationSnapshot,
    User,
)
from flipradar.services import portfolio_service


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
        del connection_record
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(bind=engine, expire_on_commit=False)() as session:
        yield session
    await engine.dispose()


async def _seed_user_and_set(db: AsyncSession) -> tuple[User, LegoSet]:
    suffix = uuid4().hex[:8]
    user = User(
        username=f"snapshot-{suffix}",
        email=f"snapshot-{suffix}@example.com",
        hashed_password="hashed",
    )
    lego_set = LegoSet(
        set_number=f"75{suffix[:4]}".upper(),
        name="Snapshot Test Set",
        theme="Icons",
        release_year=2024,
        retirement_year=2026,
        piece_count=100,
        minifig_count=1,
    )
    db.add_all([user, lego_set])
    await db.flush()
    return user, lego_set


@pytest.mark.asyncio
async def test_portfolio_change_creates_user_and_item_valuation_snapshots(
    db_session: AsyncSession,
):
    user, lego_set = await _seed_user_and_set(db_session)

    await portfolio_service.add_item_to_portfolio(
        db_session,
        user.id,
        PortfolioItemCreate(
            set_number=lego_set.set_number,
            quantity=2,
            purchase_price=Decimal("50.00"),
            condition="new",
            currency="USD",
        ),
    )

    portfolio_snapshot = (
        await db_session.execute(select(PortfolioValuationSnapshot))
    ).scalar_one()
    item_snapshot = (
        await db_session.execute(select(PortfolioItemValuationSnapshot))
    ).scalar_one()
    assert portfolio_snapshot.user_id == user.id
    assert portfolio_snapshot.cost_basis == Decimal("100.00")
    assert portfolio_snapshot.market_value == Decimal("0.00")
    assert portfolio_snapshot.currency == "USD"
    assert item_snapshot.portfolio_snapshot_id == portfolio_snapshot.id
    assert item_snapshot.unit_value is None
    assert item_snapshot.total_value is None
    assert item_snapshot.confidence == "missing_market_data"


@pytest.mark.asyncio
async def test_user_snapshot_is_deduplicated_within_an_hour(db_session: AsyncSession):
    user, lego_set = await _seed_user_and_set(db_session)
    await portfolio_service.add_item_to_portfolio(
        db_session,
        user.id,
        PortfolioItemCreate(
            set_number=lego_set.set_number,
            quantity=1,
            purchase_price=Decimal("50.00"),
            condition="new",
            currency="USD",
        ),
    )
    snapshot_at = datetime(2026, 7, 29, 12, 30, tzinfo=UTC)

    await portfolio_service.create_user_valuation_snapshot(
        db_session, user.id, snapshot_at=snapshot_at
    )
    await portfolio_service.create_user_valuation_snapshot(
        db_session,
        user.id,
        snapshot_at=datetime(2026, 7, 29, 12, 55, tzinfo=UTC),
    )

    snapshots = list(
        (await db_session.execute(select(PortfolioValuationSnapshot))).scalars()
    )
    matching_window = [
        snapshot
        for snapshot in snapshots
        if snapshot.window_start.replace(tzinfo=UTC)
        == datetime(2026, 7, 29, 12, tzinfo=UTC)
    ]
    assert len(matching_window) == 1
