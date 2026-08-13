import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import flipradar.domain.models  # noqa: F401
from flipradar.api.schemas import LegoSetCreate
from flipradar.database import Base, repositories
from flipradar.database.repositories import (
    DuplicateRecordError,
    bulk_create_marketplace_listings,
    create_listing,
    create_recommendation,
    get_latest_snapshots_by_set_number,
    get_recent_snapshots_by_set_number,
    get_set_by_number,
)
from flipradar.domain.models import (
    LegoSet,
    Marketplace,
    MarketplaceListing,
    Portfolio,
    PortfolioItem,
    PriceSnapshot,
    Recommendation,
    User,
)
from flipradar.services import marketplace_service, portfolio_service
from flipradar.services.listing_normalizer import normalize
from flipradar.services.price_snapshot_service import (
    get_latest_price_snapshot_by_set_number,
)
from flipradar.services.set_catalog_service import (
    InMemoryLegoSetCache,
    LegoSetCatalogService,
)

logger = logging.getLogger(__name__)


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

    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with session_factory() as session:
        logger.info("test database setup complete")
        yield session
        await session.rollback()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    logger.info("test database cleanup complete")


def make_random_lego_set() -> LegoSet:
    random_suffix = uuid4().hex[:8]
    return LegoSet(
        set_number=f"{random_suffix[:5]}-{random_suffix[5:]}".upper(),
        name=f"Random Test Set {random_suffix}",
        theme="Icons",
        subtheme="Database Tests",
        release_year=2024,
        retirement_year=2026,
        piece_count=1250,
        minifig_count=4,
    )


def make_marketplace(name_suffix: str = "") -> Marketplace:
    del name_suffix
    return Marketplace(
        name="ebay",
        display_name="eBay",
        base_url="https://www.ebay.com",
        fee_percent=Decimal("13.25"),
    )


@pytest.mark.asyncio
async def test_insert_randomized_lego_set(db_session: AsyncSession):
    lego_set = make_random_lego_set()
    logger.info("test insert lego set started set_number=%s", lego_set.set_number)

    db_session.add(lego_set)
    await db_session.commit()

    result = await db_session.execute(
        select(LegoSet).where(LegoSet.set_number == lego_set.set_number)
    )
    saved_set = result.scalar_one()

    logger.info("test insert lego set finished set_number=%s", lego_set.set_number)
    assert saved_set.id is not None
    assert saved_set.set_number == lego_set.set_number
    assert saved_set.name.startswith("Random Test Set")
    assert saved_set.piece_count == 1250


@pytest.mark.asyncio
async def test_catalog_upsert_caches_and_updates_seed_set(db_session: AsyncSession):
    cache = InMemoryLegoSetCache()
    service = LegoSetCatalogService(cache=cache)
    payload = {
        "set_number": "42071",
        "name": "Extreme Adventure",
        "theme": "Technic",
        "release_year": 2018,
        "retirement_year": 2018,
        "piece_count": 2382,
        "minifig_count": 0,
        "data_quality_flag": True,
        "completeness_flag": True,
    }

    created = await service.upsert(db_session, LegoSetCreate(**payload))
    assert created.set_number == "42071"
    assert created.completeness_flag is True
    assert await service.get(db_session, " 42071 ") is created

    payload["name"] = "Extreme Adventure (catalog refresh)"
    updated = await service.upsert(db_session, LegoSetCreate(**payload))
    assert updated.id == created.id
    assert updated.name == "Extreme Adventure (catalog refresh)"
    assert cache.get("42071") is updated


@pytest.mark.asyncio
async def test_insert_marketplace_listing(db_session: AsyncSession):
    lego_set = make_random_lego_set()
    marketplace = make_marketplace(name_suffix=f"-{uuid4().hex[:8]}")
    db_session.add_all([lego_set, marketplace])
    await db_session.flush()

    listing = MarketplaceListing(
        lego_set_id=lego_set.id,
        marketplace_id=marketplace.id,
        external_listing_id=f"listing-{uuid4().hex}",
        detected_set_number=lego_set.set_number,
        title=f"LEGO {lego_set.set_number} sealed complete set",
        url="https://www.ebay.com/itm/test-listing",
        price=Decimal("149.99"),
        shipping_price=Decimal("12.50"),
        total_price=Decimal("162.49"),
        currency="USD",
        condition="new",
        listing_status="active",
        seller_name="test-seller",
        seller_rating=Decimal("99.80"),
        is_complete=True,
        is_sealed=True,
        match_confidence=Decimal("98.50"),
        raw_payload={"source": "pytest", "randomized": True},
    )
    logger.info(
        "test insert listing started set_number=%s marketplace=%s",
        lego_set.set_number,
        marketplace.name,
    )

    db_session.add(listing)
    await db_session.commit()

    result = await db_session.execute(
        select(MarketplaceListing).where(
            MarketplaceListing.external_listing_id == listing.external_listing_id
        )
    )
    saved_listing = result.scalar_one()

    logger.info(
        "test insert listing finished set_number=%s marketplace=%s",
        lego_set.set_number,
        marketplace.name,
    )
    assert saved_listing.id is not None
    assert saved_listing.detected_set_number == lego_set.set_number
    assert saved_listing.lego_set_id == lego_set.id
    assert saved_listing.marketplace_id == marketplace.id
    assert saved_listing.total_price == Decimal("162.49")
    assert saved_listing.raw_payload is not None
    assert saved_listing.raw_payload["source"] == "pytest"


@pytest.mark.asyncio
async def test_insert_price_snapshot_and_fetch_latest_by_set_number(
    db_session: AsyncSession,
):
    lego_set = make_random_lego_set()
    marketplace = make_marketplace(name_suffix=f"-{uuid4().hex[:8]}")
    db_session.add_all([lego_set, marketplace])
    await db_session.flush()

    older_snapshot = PriceSnapshot(
        lego_set_id=lego_set.id,
        marketplace_id=marketplace.id,
        condition="new",
        currency="USD",
        low_price=Decimal("110.00"),
        median_price=Decimal("135.00"),
        average_price=Decimal("138.50"),
        high_price=Decimal("175.00"),
        fair_market_value=Decimal("140.00"),
        listing_count=9,
        source_payload={"source": "pytest", "age": "older"},
        snapshot_at=datetime.now(UTC) - timedelta(days=1),
    )
    latest_snapshot = PriceSnapshot(
        lego_set_id=lego_set.id,
        marketplace_id=marketplace.id,
        condition="new",
        currency="USD",
        low_price=Decimal("120.00"),
        median_price=Decimal("150.00"),
        average_price=Decimal("151.25"),
        high_price=Decimal("190.00"),
        fair_market_value=Decimal("152.00"),
        listing_count=12,
        source_payload={"source": "pytest", "age": "latest"},
        snapshot_at=datetime.now(UTC),
    )
    logger.info(
        "test insert snapshots started set_number=%s marketplace=%s snapshot_count=2",
        lego_set.set_number,
        marketplace.name,
    )

    db_session.add_all([older_snapshot, latest_snapshot])
    await db_session.commit()

    fetched_snapshot = await get_latest_price_snapshot_by_set_number(
        db_session, lego_set.set_number
    )

    logger.info(
        "test fetch latest snapshot finished set_number=%s marketplace=%s snapshot_count=1",
        lego_set.set_number,
        marketplace.name,
    )
    assert fetched_snapshot is not None
    assert fetched_snapshot.id == latest_snapshot.id
    assert fetched_snapshot.fair_market_value == Decimal("152.00")
    assert fetched_snapshot.source_payload is not None
    assert fetched_snapshot.source_payload["age"] == "latest"


@pytest.mark.asyncio
async def test_repository_functions_fetch_snapshots_and_create_recommendation(
    db_session: AsyncSession,
):
    lego_set = make_random_lego_set()
    marketplace = make_marketplace(name_suffix=f"-{uuid4().hex[:8]}")
    db_session.add_all([lego_set, marketplace])
    await db_session.flush()

    snapshots = [
        PriceSnapshot(
            lego_set_id=lego_set.id,
            marketplace_id=marketplace.id,
            condition="new",
            currency="USD",
            median_price=Decimal("130.00"),
            fair_market_value=Decimal("131.00"),
            listing_count=7,
            source_payload={"order": "oldest"},
            snapshot_at=datetime.now(UTC) - timedelta(days=2),
        ),
        PriceSnapshot(
            lego_set_id=lego_set.id,
            marketplace_id=marketplace.id,
            condition="new",
            currency="USD",
            median_price=Decimal("140.00"),
            fair_market_value=Decimal("142.00"),
            listing_count=9,
            source_payload={"order": "middle"},
            snapshot_at=datetime.now(UTC) - timedelta(days=1),
        ),
        PriceSnapshot(
            lego_set_id=lego_set.id,
            marketplace_id=marketplace.id,
            condition="new",
            currency="USD",
            median_price=Decimal("150.00"),
            fair_market_value=Decimal("152.00"),
            listing_count=12,
            source_payload={"order": "latest"},
            snapshot_at=datetime.now(UTC),
        ),
    ]
    db_session.add_all(snapshots)
    await db_session.commit()

    fetched_set = await get_set_by_number(db_session, lego_set.set_number)
    latest_snapshots = await get_latest_snapshots_by_set_number(
        db_session, lego_set.set_number
    )
    recent_snapshots = await get_recent_snapshots_by_set_number(
        db_session, lego_set.set_number, limit=2
    )
    recommendation = await create_recommendation(
        db_session,
        {
            "lego_set_id": lego_set.id,
            "goal": "buy_set",
            "decision": "BUY",
            "reason": "Repository test recommendation.",
            "confidence_score": Decimal("88.00"),
            "asking_price": Decimal("125.00"),
            "fair_market_value": Decimal("152.00"),
            "market_summary": {"source": "repository-test"},
        },
    )

    logger.info(
        "test repositories finished set_number=%s recommendation=%s snapshot_count=%s",
        lego_set.set_number,
        recommendation.decision,
        len(latest_snapshots),
    )
    assert fetched_set is not None
    assert fetched_set.id == lego_set.id
    latest_orders = []
    for snapshot in latest_snapshots:
        assert snapshot.source_payload is not None
        latest_orders.append(snapshot.source_payload["order"])
    assert latest_orders == ["latest"]

    recent_orders = []
    for snapshot in recent_snapshots:
        assert snapshot.source_payload is not None
        recent_orders.append(snapshot.source_payload["order"])
    assert recent_orders == ["latest", "middle"]
    assert recommendation.id is not None
    assert recommendation.decision == "BUY"

    saved_recommendation = await db_session.get(Recommendation, recommendation.id)
    assert saved_recommendation is not None
    assert saved_recommendation.market_summary is not None
    assert saved_recommendation.market_summary["source"] == "repository-test"


def test_listing_normalizer_handles_marketplace_payload_shapes():
    listings = normalize(
        [
            {
                "marketplace": "ebay",
                "id": "ebay-1",
                "price": "149.995",
                "shipping": "12.5",
                "condition": "Pre-Owned",
                "title": "LEGO test eBay listing",
                "listing_url": "https://www.ebay.com/itm/ebay-1",
                "seller": "ebay-seller",
            },
            {
                "marketplace": "bricklink",
                "listing_id": "bricklink-1",
                "unit_price": 140,
                "shipping_price": 10,
                "condition": "N",
                "item_name": "LEGO test BrickLink listing",
                "url": "https://www.bricklink.com/test",
                "seller_name": "bricklink-seller",
                "currency_code": "usd",
            },
        ]
    )

    assert listings == [
        {
            "marketplace": "ebay",
            "external_listing_id": "ebay-1",
            "price": Decimal("150.00"),
            "shipping_price": Decimal("12.50"),
            "condition": "used",
            "title": "LEGO test eBay listing",
            "listing_url": "https://www.ebay.com/itm/ebay-1",
            "seller": "ebay-seller",
            "currency": "USD",
            "raw_payload": {
                "marketplace": "ebay",
                "id": "ebay-1",
                "price": "149.995",
                "shipping": "12.5",
                "condition": "Pre-Owned",
                "title": "LEGO test eBay listing",
                "listing_url": "https://www.ebay.com/itm/ebay-1",
                "seller": "ebay-seller",
            },
        },
        {
            "marketplace": "bricklink",
            "external_listing_id": "bricklink-1",
            "price": Decimal("140.00"),
            "shipping_price": Decimal("10.00"),
            "condition": "new",
            "title": "LEGO test BrickLink listing",
            "listing_url": "https://www.bricklink.com/test",
            "seller": "bricklink-seller",
            "currency": "USD",
            "raw_payload": {
                "marketplace": "bricklink",
                "listing_id": "bricklink-1",
                "unit_price": 140,
                "shipping_price": 10,
                "condition": "N",
                "item_name": "LEGO test BrickLink listing",
                "url": "https://www.bricklink.com/test",
                "seller_name": "bricklink-seller",
                "currency_code": "usd",
            },
        },
    ]


@pytest.mark.asyncio
async def test_marketplace_service_updates_listings_and_snapshot(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    lego_set = make_random_lego_set()
    db_session.add(lego_set)
    await db_session.flush()

    monkeypatch.setattr(
        marketplace_service.ebay_adapter,
        "fetch_listings",
        lambda set_number: [
            {
                "id": f"ebay-{index}",
                "marketplace": "ebay",
                "price": 100 + index,
                "shipping": 10,
                "condition": "New",
                "title": f"LEGO {set_number} eBay listing {index}",
                "listing_url": f"https://www.ebay.com/itm/{index}",
                "seller": "ebay-test-seller",
                "currency": "USD",
            }
            for index in range(6)
        ],
    )
    monkeypatch.setattr(
        marketplace_service.bricklink_adapter,
        "fetch_listings",
        lambda set_number: [
            {
                "listing_id": f"bricklink-{index}",
                "marketplace": "bricklink",
                "unit_price": 120 + index,
                "shipping_price": 5,
                "condition": "U",
                "item_name": f"LEGO {set_number} BrickLink listing {index}",
                "url": f"https://www.bricklink.com/{index}",
                "seller_name": "bricklink-test-seller",
                "currency_code": "USD",
            }
            for index in range(6)
        ],
    )

    snapshot = await marketplace_service.update_marketplace_data(
        lego_set.set_number, db=db_session
    )

    saved_listings = await db_session.execute(
        select(MarketplaceListing).where(MarketplaceListing.lego_set_id == lego_set.id)
    )
    listings = list(saved_listings.scalars())

    assert len(listings) == 12
    assert {listing.detected_set_number for listing in listings} == {lego_set.set_number}
    assert {listing.match_confidence for listing in listings} == {Decimal("100.00")}
    assert {tuple(listing.match_reasons or []) for listing in listings} == {
        ("exact_set_number",)
    }
    assert {tuple(listing.exclusion_flags or []) for listing in listings} == {()}
    assert snapshot.id is not None
    assert snapshot.listing_count == 6
    assert snapshot.condition == "used"
    assert snapshot.low_price == Decimal("125.00")
    assert snapshot.high_price == Decimal("130.00")
    assert snapshot.average_price == Decimal("127.50")
    assert snapshot.median_price == Decimal("127.50")
    assert snapshot.fair_market_value == Decimal("127.50")
    assert snapshot.source_payload is not None
    assert snapshot.source_payload["marketplaces"] == ["bricklink"]

    saved_snapshots = await db_session.execute(
        select(PriceSnapshot).where(PriceSnapshot.lego_set_id == lego_set.id)
    )
    snapshots = list(saved_snapshots.scalars())
    assert len(snapshots) == 2
    assert sum(item.listing_count for item in snapshots) == 12


@pytest.mark.asyncio
async def test_bulk_listing_repository_skips_duplicates(db_session: AsyncSession):
    lego_set = make_random_lego_set()
    marketplace = make_marketplace()
    db_session.add_all([lego_set, marketplace])
    await db_session.flush()

    listing_data = {
        "external_listing_id": "bulk-duplicate",
        "title": "LEGO bulk duplicate test",
        "url": "https://www.ebay.com/itm/bulk-duplicate",
        "price": Decimal("100.00"),
        "shipping_price": Decimal("10.00"),
        "total_price": Decimal("110.00"),
        "currency": "USD",
        "condition": "new",
        "listing_status": "active",
    }

    created = await bulk_create_marketplace_listings(
        db_session,
        lego_set_id=lego_set.id,
        marketplace_id=marketplace.id,
        listings_data=[listing_data, dict(listing_data)],
    )
    skipped = await bulk_create_marketplace_listings(
        db_session,
        lego_set_id=lego_set.id,
        marketplace_id=marketplace.id,
        listings_data=[listing_data],
    )

    assert len(created) == 1
    assert skipped == []


@pytest.mark.asyncio
async def test_stale_marketplace_listings_are_removed_after_ninety_days(
    db_session: AsyncSession,
):
    lego_set = make_random_lego_set()
    marketplace = make_marketplace()
    db_session.add_all([lego_set, marketplace])
    await db_session.flush()

    listing = await create_listing(
        db_session,
        lego_set_id=lego_set.id,
        marketplace_id=marketplace.id,
        listing_data={
            "external_listing_id": "stale-listing",
            "title": "LEGO stale listing",
            "url": "https://www.ebay.com/itm/stale-listing",
            "price": Decimal("100.00"),
            "shipping_price": Decimal("10.00"),
            "total_price": Decimal("110.00"),
            "currency": "USD",
            "condition": "new",
            "listing_status": "active",
        },
    )
    listing.last_seen_at = datetime.now(UTC) - timedelta(days=91)
    await db_session.flush()

    stale_count = await repositories.mark_stale_marketplace_listings(
        db_session,
        lego_set_id=lego_set.id,
        stale_before=datetime.now(UTC) - timedelta(days=90),
    )
    await db_session.refresh(listing)

    assert stale_count == 1
    assert listing.listing_status == "removed"


@pytest.mark.asyncio
async def test_duplicate_listing_repository_maps_conflict(db_session: AsyncSession):
    lego_set = make_random_lego_set()
    marketplace = make_marketplace()
    db_session.add_all([lego_set, marketplace])
    await db_session.flush()

    listing_data = {
        "external_listing_id": "concurrent-duplicate",
        "title": "LEGO duplicate conflict test",
        "url": "https://www.ebay.com/itm/concurrent-duplicate",
        "price": Decimal("100.00"),
        "shipping_price": Decimal("10.00"),
        "total_price": Decimal("110.00"),
        "currency": "USD",
        "condition": "new",
        "listing_status": "active",
    }
    await create_listing(
        db_session,
        lego_set_id=lego_set.id,
        marketplace_id=marketplace.id,
        listing_data=listing_data,
    )

    with pytest.raises(DuplicateRecordError):
        await create_listing(
            db_session,
            lego_set_id=lego_set.id,
            marketplace_id=marketplace.id,
            listing_data=listing_data,
        )


@pytest.mark.asyncio
async def test_portfolio_summary_batches_snapshot_queries(db_session: AsyncSession):
    user = User(
        username=f"nplusone-{uuid4().hex[:8]}",
        email=f"nplusone-{uuid4().hex[:8]}@example.com",
        hashed_password="hashed",
    )
    marketplace = make_marketplace()
    sets = [make_random_lego_set() for _ in range(3)]
    db_session.add_all([user, marketplace, *sets])
    await db_session.flush()
    portfolio = Portfolio(user_id=user.id, name="Default Portfolio", is_default=True)
    db_session.add(portfolio)
    await db_session.flush()

    for index, lego_set in enumerate(sets):
        db_session.add(
            PriceSnapshot(
                lego_set_id=lego_set.id,
                marketplace_id=marketplace.id,
                condition="new",
                currency="USD",
                median_price=Decimal("100.00") + index,
                fair_market_value=Decimal("100.00") + index,
                listing_count=10,
            )
        )
        db_session.add(
            PortfolioItem(
                user_id=user.id,
                portfolio_id=portfolio.id,
                lego_set_id=lego_set.id,
                quantity=1,
                purchase_price=Decimal("75.00"),
                condition="new",
            )
        )
    await db_session.flush()

    statement_counts = {"price_snapshots": 0}

    def count_price_snapshot_queries(
        conn, cursor, statement, parameters, context, executemany
    ):
        del conn, cursor, parameters, context, executemany
        if "price_snapshots" in statement and statement.lstrip().upper().startswith(
            "SELECT"
        ):
            statement_counts["price_snapshots"] += 1

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", count_price_snapshot_queries)
    try:
        summary = await portfolio_service.calculate_portfolio_summary(
            db_session, user.id
        )
    finally:
        event.remove(engine, "before_cursor_execute", count_price_snapshot_queries)

    assert summary["total_items"] == 3
    assert statement_counts["price_snapshots"] == 1
