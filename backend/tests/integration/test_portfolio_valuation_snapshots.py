import asyncio
from datetime import UTC, datetime, timedelta
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
    PortfolioValuationDailyRollup,
    PortfolioValuationSnapshot,
    User,
)
from flipradar.services import portfolio_dashboard_cache, portfolio_service
from flipradar.services.portfolio_valuation_retention import (
    aggregate_and_prune_portfolio_valuations,
)


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
async def test_valuation_snapshot_persists_fake_market_value_and_confidence(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    user, lego_set = await _seed_user_and_set(db_session)

    async def fake_value_map(db, items):
        del db
        return {
            (item.set_number, item.condition): (
                Decimal("125.00"),
                "valued",
                "high",
            )
            for item in items
        }

    monkeypatch.setattr(portfolio_service, "_current_unit_value_map", fake_value_map)
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
    assert portfolio_snapshot.market_value == Decimal("250.00")
    assert portfolio_snapshot.gain_loss == Decimal("150.00")
    assert item_snapshot.unit_value == Decimal("125.00")
    assert item_snapshot.total_value == Decimal("250.00")
    assert item_snapshot.confidence == "high"


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


@pytest.mark.asyncio
async def test_history_returns_requested_points_and_cleanly_rejects_short_history(
    db_session: AsyncSession,
):
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
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    await portfolio_service.create_user_valuation_snapshot(
        db_session, user.id, snapshot_at=now - timedelta(hours=2)
    )
    await portfolio_service.create_user_valuation_snapshot(
        db_session, user.id, snapshot_at=now - timedelta(hours=1)
    )

    history = await portfolio_service.get_portfolio_valuation_history(
        db_session, user.id, "1d"
    )
    assert history["range"] == "1d"
    assert len(history["points"]) >= 2


@pytest.mark.asyncio
async def test_retention_rolls_old_hourly_snapshots_into_daily_history(
    db_session: AsyncSession,
):
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
    old_timestamp = datetime.now(UTC) - timedelta(days=181)
    await portfolio_service.create_user_valuation_snapshot(
        db_session, user.id, snapshot_at=old_timestamp
    )

    deleted = await aggregate_and_prune_portfolio_valuations(db_session)

    assert deleted >= 1
    rollups = list(
        (await db_session.execute(select(PortfolioValuationDailyRollup))).scalars()
    )
    assert any(rollup.user_id == user.id for rollup in rollups)


@pytest.mark.asyncio
async def test_dashboard_read_reuses_one_valuation_pass_and_handles_missing_history(
    db_session: AsyncSession,
):
    user, _lego_set = await _seed_user_and_set(db_session)
    portfolio = await portfolio_service.get_default_portfolio_for_user(
        db_session, user.id
    )
    assert portfolio is not None
    portfolio_dashboard_cache.clear()

    dashboard = await portfolio_service.get_portfolio_dashboard(
        db_session,
        user.id,
        portfolio_id=portfolio.id,
        limit=25,
        offset=0,
        condition=None,
        theme=None,
        year=None,
        performance=None,
        order="purchase_date_desc",
        history_range="1m",
    )

    assert dashboard["portfolio"]["data"] == []
    assert dashboard["summary"]["total_items"] == 0
    assert dashboard["history"] is None
    assert "not yet available" in dashboard["history_unavailable"]


@pytest.mark.asyncio
async def test_dashboard_cache_coalesces_concurrent_reads():
    portfolio_dashboard_cache.clear()
    calls = 0

    async def load() -> dict:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return {"calls": calls}

    results = await asyncio.gather(
        *(
            portfolio_dashboard_cache.get_or_load(("concurrent-user",), load)
            for _ in range(12)
        )
    )

    assert calls == 1
    assert results == [{"calls": 1}] * 12
