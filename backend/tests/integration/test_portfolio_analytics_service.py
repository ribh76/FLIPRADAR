from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import flipradar.domain.models  # noqa: F401
from flipradar.database import Base
from flipradar.domain.models import (
    LegoSet,
    Marketplace,
    MarketplaceListing,
    PortfolioAnalysis,
    PortfolioAnalyticsSnapshot,
    PortfolioHoldingAnalytics,
    PortfolioItem,
    PriceSnapshot,
    User,
)
from flipradar.services import portfolio_analysis_service, portfolio_analytics_service

ANALYSIS_AT = datetime(2026, 8, 1, 12, tzinfo=UTC)


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


async def _seed_analytics_data(db: AsyncSession) -> User:
    user = User(
        username="portfolio-analytics",
        email="portfolio-analytics@example.com",
        hashed_password="hashed",
    )
    ebay = Marketplace(name="ebay", display_name="eBay", fee_percent=Decimal("13"))
    bricklink = Marketplace(
        name="bricklink", display_name="BrickLink", fee_percent=Decimal("3")
    )
    rising = LegoSet(
        set_number="900001",
        name="Rising Set",
        theme="Icons",
        release_year=2021,
    )
    falling = LegoSet(
        set_number="900002",
        name="Falling Set",
        theme="Technic",
        release_year=2023,
    )
    unvalued = LegoSet(
        set_number="900003",
        name="Unvalued Set",
        theme="Icons",
        release_year=2020,
    )
    db.add_all([user, ebay, bricklink, rising, falling, unvalued])
    await db.flush()
    acquired_at = ANALYSIS_AT - timedelta(days=365)
    db.add_all(
        [
            PortfolioItem(
                user_id=user.id,
                lego_set_id=rising.id,
                quantity=1,
                purchase_price=Decimal("100.00"),
                condition="new",
                purchase_date=acquired_at,
                created_at=acquired_at,
            ),
            PortfolioItem(
                user_id=user.id,
                lego_set_id=falling.id,
                quantity=1,
                purchase_price=Decimal("150.00"),
                condition="new",
                purchase_date=acquired_at,
                created_at=acquired_at,
            ),
            PortfolioItem(
                user_id=user.id,
                lego_set_id=unvalued.id,
                quantity=1,
                purchase_price=Decimal("50.00"),
                condition="used",
                created_at=acquired_at,
            ),
        ]
    )
    price_snapshots = []
    for lego_set, old_value, current_value in (
        (rising, "100.00", "200.00"),
        (falling, "150.00", "120.00"),
    ):
        for value, retrieval_time in (
            (old_value, ANALYSIS_AT - timedelta(days=30)),
            (current_value, ANALYSIS_AT),
        ):
            price_snapshots.append(
                PriceSnapshot(
                    lego_set_id=lego_set.id,
                    marketplace_id=ebay.id,
                    condition="new",
                    metric_type="fair_market_value",
                    value=Decimal(value),
                    sample_size=12,
                    retrieval_time=retrieval_time,
                )
            )
        price_snapshots.extend(
            [
                PriceSnapshot(
                    lego_set_id=lego_set.id,
                    marketplace_id=bricklink.id,
                    condition="new",
                    metric_type="low",
                    value=Decimal("90.00"),
                    sample_size=12,
                    retrieval_time=ANALYSIS_AT,
                ),
                PriceSnapshot(
                    lego_set_id=lego_set.id,
                    marketplace_id=bricklink.id,
                    condition="new",
                    metric_type="high",
                    value=Decimal("225.00"),
                    sample_size=12,
                    retrieval_time=ANALYSIS_AT,
                ),
            ]
        )
    db.add_all(price_snapshots)
    for index in range(3):
        db.add(
            MarketplaceListing(
                lego_set_id=rising.id,
                marketplace_id=ebay.id,
                external_listing_id=f"rising-{index}",
                title="Verified active listing",
                url=f"https://example.test/rising-{index}",
                price=Decimal("200.00"),
                shipping_price=Decimal("0.00"),
                total_price=Decimal("200.00"),
                condition="new",
                listing_status="active",
                is_verified=True,
                first_seen_at=ANALYSIS_AT - timedelta(days=1),
                last_seen_at=ANALYSIS_AT - timedelta(days=1),
            )
        )
    await db.flush()
    return user


@pytest.mark.asyncio
async def test_refresh_calculates_persists_and_retrieves_deterministic_analytics(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    user = await _seed_analytics_data(db_session)

    async def fixed_value_map(_db, items):
        del _db
        values = {
            "900001": (Decimal("200.00"), "valued", "high"),
            "900002": (Decimal("120.00"), "valued", "low"),
            "900003": (None, "missing_market_data", "missing_market_data"),
        }
        return {
            (item.set_number, item.condition): values[item.set_number] for item in items
        }

    monkeypatch.setattr(
        portfolio_analytics_service, "_current_unit_value_map", fixed_value_map
    )

    result = await portfolio_analytics_service.refresh_portfolio_analytics(
        db_session, user.id, analysis_at=ANALYSIS_AT
    )

    assert result["generated_at"] == ANALYSIS_AT
    assert result["holding_count"] == 3
    assert result["valued_holding_count"] == 2
    assert result["total_cost_basis"] == Decimal("300.00")
    assert result["total_market_value"] == Decimal("320.00")

    holdings = {holding["set_number"]: holding for holding in result["holdings"]}
    rising = holdings["900001"]
    falling = holdings["900002"]
    unvalued = holdings["900003"]
    assert rising["performance_percent"] == Decimal("100.00")
    assert rising["holding_days"] == 365
    assert rising["trend_label"] == "rising"
    assert rising["trend_percent"] == Decimal("100.00")
    assert rising["marketplace_supply"] == 3
    assert rising["supply_reliable"] is True
    assert rising["signal"] == "sell_consideration"
    assert falling["performance_percent"] == Decimal("-20.00")
    assert falling["trend_label"] == "falling"
    assert falling["valuation_confidence"] == "low"
    assert falling["signal"] == "hold"
    assert unvalued["holding_days"] == 365
    assert unvalued["current_total_value"] is None
    assert {
        "insufficient_market_data",
        "low_confidence_valuation",
        "stale_valuation",
    }.issubset(unvalued["flags"])

    summary = result["summary_metrics"]
    assert summary["allocation"]["theme"] == [
        {
            "key": "Icons",
            "holding_count": 2,
            "quantity": 2,
            "market_value": "200.00",
            "unvalued_holding_count": 1,
            "portfolio_value_percent": "62.50",
        },
        {
            "key": "Technic",
            "holding_count": 1,
            "quantity": 1,
            "market_value": "120.00",
            "unvalued_holding_count": 0,
            "portfolio_value_percent": "37.50",
        },
    ]
    assert summary["allocation"]["condition"][1]["key"] == "used"
    assert summary["allocation"]["release_year"][0]["key"] == "2021"
    assert summary["concentration"]["level"] == "high"
    assert summary["concentration"]["hhi"] == "5312.50"
    assert summary["concentration"]["largest_holding_percent"] == "62.50"
    assert summary["diversification"] == {
        "distinct_sets": 3,
        "distinct_themes": 2,
        "distinct_conditions": 2,
        "distinct_release_years": 3,
        "theme_hhi": "5312.50",
        "value_coverage_percent": "66.67",
    }
    assert summary["top_performers"][0]["set_number"] == "900001"
    assert summary["bottom_performers"][0]["set_number"] == "900002"
    assert summary["signals"] == {
        "hold": 2,
        "watch": 0,
        "sell_consideration": 1,
    }
    assert [item["set_number"] for item in summary["valuation_attention"]["stale"]] == [
        "900003"
    ]

    stored_snapshots = list(
        (await db_session.execute(select(PortfolioAnalyticsSnapshot))).scalars()
    )
    stored_holdings = list(
        (await db_session.execute(select(PortfolioHoldingAnalytics))).scalars()
    )
    assert len(stored_snapshots) == 1
    assert len(stored_holdings) == 3
    assert stored_snapshots[0].summary_metrics == summary
    assert {holding.signal for holding in stored_holdings} == {
        "hold",
        "sell_consideration",
    }

    latest = await portfolio_analytics_service.get_latest_portfolio_analytics(
        db_session, user.id
    )
    assert latest["id"] == result["id"]


@pytest.mark.asyncio
async def test_completed_portfolio_analysis_persists_confidence_and_data_quality(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    user = await _seed_analytics_data(db_session)

    async def fixed_value_map(_db, items):
        del _db
        values = {
            "900001": (Decimal("200.00"), "valued", "high"),
            "900002": (Decimal("120.00"), "valued", "low"),
            "900003": (None, "missing_market_data", "missing_market_data"),
        }
        return {
            (item.set_number, item.condition): values[item.set_number] for item in items
        }

    monkeypatch.setattr(
        portfolio_analytics_service, "_current_unit_value_map", fixed_value_map
    )

    result = await portfolio_analysis_service.analyze_portfolio(db_session, user.id)

    stored = list((await db_session.execute(select(PortfolioAnalysis))).scalars())
    assert len(stored) == 1
    assert stored[0].id == result["id"]
    assert stored[0].analytics_snapshot_id == result["analytics"]["id"]
    assert stored[0].method_version == "portfolio-analysis-method-v1"
    assert stored[0].prompt_version == "portfolio-analysis-v1"
    assert stored[0].portfolio_context["id"] == str(result["analytics"]["id"])
    assert stored[0].confidence_summary == result["confidence_summary"]
    assert stored[0].data_quality_warnings == result["data_quality_warnings"]
    assert stored[0].item_recommendations[0]["priority"] >= 1
    assert result["confidence_summary"]["overall"] == "low"
    assert any(
        warning["code"] == "insufficient_market_data"
        for warning in result["data_quality_warnings"]
    )


@pytest.mark.asyncio
async def test_history_retrieval_and_comparison_preserve_context_and_changes(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    user = await _seed_analytics_data(db_session)

    async def fixed_value_map(_db, items):
        del _db
        values = {
            "900001": (Decimal("200.00"), "valued", "high"),
            "900002": (Decimal("120.00"), "valued", "low"),
            "900003": (None, "missing_market_data", "missing_market_data"),
        }
        return {
            (item.set_number, item.condition): values[item.set_number] for item in items
        }

    monkeypatch.setattr(
        portfolio_analytics_service, "_current_unit_value_map", fixed_value_map
    )
    first = await portfolio_analysis_service.analyze_portfolio(db_session, user.id)
    second = await portfolio_analysis_service.analyze_portfolio(db_session, user.id)

    second_record = await db_session.get(PortfolioAnalysis, second["id"])
    assert second_record is not None
    second_recommendations = [dict(item) for item in second_record.item_recommendations]
    target = next(
        item for item in second_recommendations if item["set_number"] == "900001"
    )
    target["label"] = (
        "hold" if target["label"] == "consider_selling" else "consider_selling"
    )
    second_record.item_recommendations = second_recommendations
    await db_session.flush()

    history = await portfolio_analysis_service.get_portfolio_analysis_history(
        db_session, user.id, limit=25, offset=0
    )
    comparison = await portfolio_analysis_service.compare_portfolio_analyses(
        db_session,
        user.id,
        previous_analysis_id=first["id"],
        current_analysis_id=second["id"],
    )

    assert [entry["id"] for entry in history] == [second["id"], first["id"]]
    assert history[0]["method_version"] == "portfolio-analysis-method-v1"
    assert history[0]["portfolio_context"]["holding_count"] == 3
    changed = next(
        change for change in comparison["changes"] if change["set_number"] == "900001"
    )
    assert changed["change_type"] == "changed"
    assert changed["is_reversal"] is True
    assert comparison["trend_summary"]["changed_recommendation_count"] >= 1

    updated = await portfolio_analysis_service.update_analysis_metadata(
        db_session,
        user.id,
        first["id"],
        labels=["monthly review"],
        annotation="Check again after valuation refresh.",
    )
    assert updated["labels"] == ["monthly review"]
    assert updated["annotation"] == "Check again after valuation refresh."
    await portfolio_analysis_service.remove_portfolio_analysis(
        db_session, user.id, first["id"]
    )
    remaining = await portfolio_analysis_service.get_portfolio_analysis_history(
        db_session, user.id, limit=25, offset=0
    )
    assert [entry["id"] for entry in remaining] == [second["id"]]
