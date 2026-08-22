"""Create idempotent, representative local data for FlipRadar development.

The seed is deliberately broad: it exercises different themes, set states, price
trends, marketplace listing states, and the authenticated portfolio views.  It is
safe to run repeatedly; every record has a stable demo key or timestamp.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from path_setup import ensure_backend_path

ensure_backend_path()

from flipradar.api.dependencies.auth import hash_password
from flipradar.database import SessionLocal, create_database_tables
from flipradar.domain.models import (
    Element,
    InventoryItem,
    LegoSet,
    Marketplace,
    MarketplaceListing,
    Portfolio,
    PortfolioAnalysis,
    PortfolioAnalyticsSnapshot,
    PortfolioHoldingAnalytics,
    PortfolioItem,
    PriceSnapshot,
    SetPartRequirement,
    User,
    WatchlistItem,
    WatchlistPriceHistory,
)
from flipradar.services.errors import ServiceProviderUnavailableError
from flipradar.services.part_catalog_service import synchronize_parts

logger = logging.getLogger(__name__)

DEMO_NOW = datetime(2026, 8, 10, 16, 0, tzinfo=UTC)
DEMO_EMAIL = "demo@flipradar.com"

DEMO_SETS = [
    (
        "75192",
        "Millennium Falcon",
        "Star Wars",
        "Ultimate Collector Series",
        2017,
        2024,
        7541,
        8,
        "849.99",
        "790.00",
        "905.00",
        "1025.00",
    ),
    (
        "75313",
        "AT-AT",
        "Star Wars",
        "Ultimate Collector Series",
        2021,
        2024,
        6785,
        9,
        "849.99",
        "620.00",
        "705.00",
        "790.00",
    ),
    (
        "10307",
        "Eiffel Tower",
        "Icons",
        "Landmarks",
        2022,
        None,
        10001,
        0,
        "629.99",
        "530.00",
        "610.00",
        "700.00",
    ),
    (
        "10294",
        "Titanic",
        "Icons",
        "Historical",
        2021,
        None,
        9090,
        0,
        "679.99",
        "590.00",
        "660.00",
        "735.00",
    ),
    (
        "21335",
        "Motorized Lighthouse",
        "Ideas",
        None,
        2022,
        2024,
        2065,
        2,
        "299.99",
        "350.00",
        "405.00",
        "470.00",
    ),
    (
        "71411",
        "The Mighty Bowser",
        "Super Mario",
        None,
        2022,
        None,
        2807,
        0,
        "269.99",
        "205.00",
        "235.00",
        "275.00",
    ),
    (
        "76989",
        "Horizon Forbidden West: Tallneck",
        "Horizon",
        None,
        2022,
        2024,
        1222,
        1,
        "89.99",
        "105.00",
        "135.00",
        "160.00",
    ),
    (
        "42083",
        "Bugatti Chiron",
        "Technic",
        "Ultimate Car Concept",
        2018,
        2021,
        3599,
        0,
        "349.99",
        "315.00",
        "375.00",
        "440.00",
    ),
]

LISTINGS = [
    (
        "ebay-75192-deal",
        "ebay",
        "75192",
        "LEGO Star Wars 75192 Millennium Falcon - sealed",
        "760.00",
        "28.00",
        "new",
        "active",
        "brickbybrick",
        "99.80",
        True,
        True,
        "98.00",
    ),
    (
        "bricklink-75192",
        "bricklink",
        "75192",
        "75192 Millennium Falcon, new and sealed",
        "925.00",
        "0.00",
        "new",
        "active",
        "NorthwestBricks",
        "100.00",
        True,
        True,
        "99.00",
    ),
    (
        "ebay-75313-used",
        "ebay",
        "75313",
        "LEGO 75313 AT-AT complete with minifigures",
        "515.00",
        "42.00",
        "used",
        "active",
        "galaxycollector",
        "98.10",
        True,
        False,
        "96.00",
    ),
    (
        "bricklink-21335",
        "bricklink",
        "21335",
        "21335 Motorized Lighthouse sealed",
        "395.00",
        "12.00",
        "new",
        "active",
        "IdeasVault",
        "100.00",
        True,
        True,
        "99.00",
    ),
    (
        "ebay-76989-sold",
        "ebay",
        "76989",
        "LEGO 76989 Tallneck complete sealed",
        "122.00",
        "11.00",
        "new",
        "sold",
        "retiredfinds",
        "99.40",
        True,
        True,
        "98.00",
    ),
    (
        "ebay-71411-ended",
        "ebay",
        "71411",
        "The Mighty Bowser 71411, open box",
        "175.00",
        "19.00",
        "used",
        "ended",
        "toyattic",
        "95.00",
        False,
        False,
        "80.00",
    ),
]


async def _one_or_create(session, model, where, **values):
    instance = (await session.execute(select(model).where(*where))).scalar_one_or_none()
    if instance is None:
        instance = model(**values)
        session.add(instance)
        await session.flush()
    return instance


async def seed() -> None:
    await create_database_tables()
    async with SessionLocal() as session:
        ebay = await _one_or_create(
            session,
            Marketplace,
            [Marketplace.name == "ebay"],
            name="ebay",
            display_name="eBay",
            base_url="https://www.ebay.com",
            fee_percent=Decimal("13.25"),
        )
        bricklink = await _one_or_create(
            session,
            Marketplace,
            [Marketplace.name == "bricklink"],
            name="bricklink",
            display_name="BrickLink",
            base_url="https://www.bricklink.com",
            fee_percent=Decimal("3.00"),
        )
        markets = {"ebay": ebay, "bricklink": bricklink}

        sets = {}
        for (
            number,
            name,
            theme,
            subtheme,
            release,
            retired,
            pieces,
            figs,
            msrp,
            _low,
            _median,
            _high,
        ) in DEMO_SETS:
            sets[number] = await _one_or_create(
                session,
                LegoSet,
                [LegoSet.set_number == number],
                set_number=number,
                name=name,
                theme=theme,
                subtheme=subtheme,
                release_year=release,
                retirement_year=retired,
                piece_count=pieces,
                minifig_count=figs,
                msrp=Decimal(msrp),
                original_currency="USD",
                region="US",
                source_name="FlipRadar demo catalog",
                completeness_flag=True,
            )

        # Keep representative part records synchronized through the same path
        # used by catalog retrieval.
        try:
            await synchronize_parts(session, "3001")
        except ServiceProviderUnavailableError:
            logger.warning(
                "skipping optional part catalog seed because BrickLink is unavailable"
            )

        # Three points per set make 90-day trends, while both conditions cover valuation paths.
        for index, row in enumerate(DEMO_SETS):
            number, *_metadata, low, median, high = row
            base = Decimal(median)
            starting_factor = (
                Decimal("0.90")
                if number in {"75192", "21335", "76989", "42083"}
                else Decimal("1.06")
            )
            for days_ago, factor in (
                (84, starting_factor),
                (42, (starting_factor + Decimal("1")) / 2),
                (0, Decimal("1")),
            ):
                retrieved = DEMO_NOW - timedelta(days=days_ago, minutes=index)
                for market_name, market_adjustment in (
                    ("ebay", Decimal("1.00")),
                    ("bricklink", Decimal("1.03")),
                ):
                    market = markets[market_name]
                    value = (base * factor * market_adjustment).quantize(
                        Decimal("0.01")
                    )
                    for metric, multiplier in (
                        ("low", Decimal("0.88")),
                        ("median", Decimal("0.98")),
                        ("average", Decimal("1.00")),
                        ("high", Decimal("1.13")),
                        ("fair_market_value", Decimal("1.00")),
                    ):
                        snapshot_time = retrieved + timedelta(
                            seconds={
                                "low": 1,
                                "median": 2,
                                "average": 3,
                                "high": 4,
                                "fair_market_value": 5,
                            }[metric]
                        )
                        await _one_or_create(
                            session,
                            PriceSnapshot,
                            [
                                PriceSnapshot.lego_set_id == sets[number].id,
                                PriceSnapshot.marketplace_id == market.id,
                                PriceSnapshot.condition == "new",
                                PriceSnapshot.metric_type == metric,
                                PriceSnapshot.retrieval_time == snapshot_time,
                            ],
                            lego_set_id=sets[number].id,
                            marketplace_id=market.id,
                            condition="new",
                            currency="USD",
                            metric_type=metric,
                            value=(value * multiplier).quantize(Decimal("0.01")),
                            sample_size=12 + index,
                            retrieval_time=snapshot_time,
                            source_payload={
                                "source": "demo-seed",
                                "evidence_counts": {
                                    "sold": 9 + index,
                                    "active": 6 + index,
                                },
                            },
                        )
                # A current used-complete price is enough to exercise used holdings.
                used_time = retrieved + timedelta(seconds=10)
                await _one_or_create(
                    session,
                    PriceSnapshot,
                    [
                        PriceSnapshot.lego_set_id == sets[number].id,
                        PriceSnapshot.marketplace_id == ebay.id,
                        PriceSnapshot.condition == "used_complete",
                        PriceSnapshot.metric_type == "fair_market_value",
                        PriceSnapshot.retrieval_time == used_time,
                    ],
                    lego_set_id=sets[number].id,
                    marketplace_id=ebay.id,
                    condition="used_complete",
                    currency="USD",
                    metric_type="fair_market_value",
                    value=(value * Decimal("0.72")).quantize(Decimal("0.01")),
                    sample_size=8 + index,
                    retrieval_time=used_time,
                    source_payload={
                        "source": "demo-seed",
                        "evidence_counts": {"sold": 5, "active": 7},
                    },
                )

        listings = {}
        for (
            external_id,
            market_name,
            set_number,
            title,
            price,
            shipping,
            condition,
            status,
            seller,
            rating,
            complete,
            sealed,
            confidence,
        ) in LISTINGS:
            total = Decimal(price) + Decimal(shipping)
            listings[external_id] = await _one_or_create(
                session,
                MarketplaceListing,
                [
                    MarketplaceListing.marketplace_id == markets[market_name].id,
                    MarketplaceListing.external_listing_id == external_id,
                ],
                lego_set_id=sets[set_number].id,
                marketplace_id=markets[market_name].id,
                external_listing_id=external_id,
                detected_set_number=set_number,
                title=title,
                url=f"https://example.invalid/demo/{external_id}",
                price=Decimal(price),
                shipping_price=Decimal(shipping),
                total_price=total,
                currency="USD",
                condition=condition,
                listing_status=status,
                seller_name=seller,
                seller_rating=Decimal(rating),
                is_complete=complete,
                is_sealed=sealed,
                match_confidence=Decimal(confidence),
                match_reasons=["set number matches", "title match"],
                exclusion_flags=[],
                raw_payload={"source": "demo-seed"},
                is_verified=True,
                first_seen_at=DEMO_NOW - timedelta(days=7),
                last_seen_at=DEMO_NOW,
            )

        user = await _one_or_create(
            session,
            User,
            [User.email == DEMO_EMAIL],
            username="demo",
            display_name="Demo Collector",
            email=DEMO_EMAIL,
            hashed_password=hash_password("DemoPass1!"),
            is_email_verified=True,
            email_verified_at=DEMO_NOW - timedelta(days=30),
        )
        default_portfolio = await _one_or_create(
            session,
            Portfolio,
            [Portfolio.user_id == user.id, Portfolio.is_default.is_(True)],
            user_id=user.id,
            name="Demo Collection",
            description="Representative seeded LEGO holdings.",
            currency="USD",
            is_default=True,
        )
        # A small owned-parts inventory and BOM make the rebuild workflow usable
        # immediately after a development seed.
        elements = (
            (
                await session.execute(
                    select(Element).order_by(Element.canonical_identifier)
                )
            )
            .scalars()
            .all()
        )
        for index, element in enumerate(elements):
            await _one_or_create(
                session,
                InventoryItem,
                [
                    InventoryItem.user_id == user.id,
                    InventoryItem.element_id == element.id,
                ],
                user_id=user.id,
                element_id=element.id,
                quantity=(2 if index == 0 else 1),
            )
        for index, element in enumerate(elements):
            await _one_or_create(
                session,
                SetPartRequirement,
                [
                    SetPartRequirement.lego_set_id == sets["75192"].id,
                    SetPartRequirement.element_id == element.id,
                ],
                lego_set_id=sets["75192"].id,
                element_id=element.id,
                quantity=(4 if index == 0 else 3),
            )
        portfolio_specs = [
            ("75192", 1, "790.00", "sealed", 150),
            ("21335", 2, "285.00", "new", 310),
            ("42083", 1, "290.00", "new", 780),
            ("75313", 1, "550.00", "used", 125),
            ("71411", 1, "250.00", "new", 90),
        ]
        portfolio = {}
        for number, quantity, price, condition, age in portfolio_specs:
            portfolio[number] = await _one_or_create(
                session,
                PortfolioItem,
                [
                    PortfolioItem.user_id == user.id,
                    PortfolioItem.portfolio_id == default_portfolio.id,
                    PortfolioItem.lego_set_id == sets[number].id,
                ],
                user_id=user.id,
                portfolio_id=default_portfolio.id,
                lego_set_id=sets[number].id,
                quantity=quantity,
                purchase_price=Decimal(price),
                condition=condition,
                purchase_date=DEMO_NOW - timedelta(days=age),
                currency="USD",
                notes="Representative demo holding",
            )

        watch_set = await _one_or_create(
            session,
            WatchlistItem,
            [
                WatchlistItem.user_id == user.id,
                WatchlistItem.lego_set_id == sets["10307"].id,
            ],
            user_id=user.id,
            lego_set_id=sets["10307"].id,
            target_price=Decimal("575.00"),
            notes="Watch for a seasonal discount.",
        )
        watch_listing = await _one_or_create(
            session,
            WatchlistItem,
            [
                WatchlistItem.user_id == user.id,
                WatchlistItem.marketplace_listing_id == listings["ebay-75192-deal"].id,
            ],
            user_id=user.id,
            marketplace_listing_id=listings["ebay-75192-deal"].id,
            target_price=Decimal("800.00"),
            last_known_listing_price=Decimal("788.00"),
            last_known_listing_status="active",
            notes="Strong sealed-set opportunity.",
        )
        for watch, prices in (
            (watch_set, ("620.00", "590.00", "565.00")),
            (watch_listing, ("840.00", "815.00", "788.00")),
        ):
            for days_ago, price in zip((14, 7, 0), prices, strict=True):
                observed = DEMO_NOW - timedelta(days=days_ago)
                await _one_or_create(
                    session,
                    WatchlistPriceHistory,
                    [
                        WatchlistPriceHistory.watchlist_item_id == watch.id,
                        WatchlistPriceHistory.observed_at == observed,
                    ],
                    watchlist_item_id=watch.id,
                    listing_price=Decimal(price),
                    listing_status="active",
                    fair_value=Decimal(
                        "905.00" if watch is watch_listing else "610.00"
                    ),
                    discount_percent=Decimal("12.93"),
                    deal_score=Decimal("88.00"),
                    target_price=watch.target_price,
                    is_under_target=Decimal(price) <= watch.target_price,
                    observed_at=observed,
                )

        analytics = await _one_or_create(
            session,
            PortfolioAnalyticsSnapshot,
            [
                PortfolioAnalyticsSnapshot.user_id == user.id,
                PortfolioAnalyticsSnapshot.generated_at == DEMO_NOW,
            ],
            user_id=user.id,
            generated_at=DEMO_NOW,
            currency="USD",
            schema_version=1,
            holding_count=5,
            valued_holding_count=5,
            total_cost_basis=Decimal("2450.00"),
            total_market_value=Decimal("2845.00"),
            summary_metrics={
                "unrealized_gain_loss": "395.00",
                "performance_percent": "16.12",
                "concentration": {"level": "moderate"},
                "source": "demo-seed",
            },
        )
        for number, label, score in (
            ("75192", "hold", 78),
            ("21335", "hold", 84),
            ("42083", "consider_selling", 72),
            ("75313", "watch", 65),
            ("71411", "watch", 58),
        ):
            await _one_or_create(
                session,
                PortfolioHoldingAnalytics,
                [
                    PortfolioHoldingAnalytics.analytics_snapshot_id == analytics.id,
                    PortfolioHoldingAnalytics.portfolio_item_id == portfolio[number].id,
                ],
                analytics_snapshot_id=analytics.id,
                portfolio_item_id=portfolio[number].id,
                set_number=number,
                condition=portfolio[number].condition,
                quantity=portfolio[number].quantity,
                cost_basis=portfolio[number].purchase_price
                * portfolio[number].quantity,
                current_total_value=Decimal(
                    "905.00"
                    if number == "75192"
                    else (
                        "405.00"
                        if number == "21335"
                        else (
                            "375.00"
                            if number == "42083"
                            else "507.60" if number == "75313" else "235.00"
                        )
                    )
                ),
                performance_percent=Decimal("14.56"),
                holding_days=90,
                valuation_confidence="high",
                valuation_stale=False,
                trend_label="rising",
                trend_percent=Decimal("10.00"),
                marketplace_supply=8,
                supply_reliable=True,
                signal=label,
                signal_score=score,
                flags=[],
                metrics={"source": "demo-seed"},
            )
        await _one_or_create(
            session,
            PortfolioAnalysis,
            [
                PortfolioAnalysis.user_id == user.id,
                PortfolioAnalysis.generated_at == DEMO_NOW,
            ],
            user_id=user.id,
            analytics_snapshot_id=analytics.id,
            generated_at=DEMO_NOW,
            method_version="portfolio-analysis-v1",
            prompt_version="portfolio-analysis-v1",
            portfolio_context={
                "summary": "Representative demo analysis",
                "analytics_snapshot_id": str(analytics.id),
            },
            ai_narrative_status="disabled",
            ai_narrative=None,
            item_recommendations=[
                {
                    "portfolio_item_id": str(portfolio["42083"].id),
                    "set_number": "42083",
                    "set_name": "Bugatti Chiron",
                    "label": "consider_selling",
                    "priority": 1,
                    "confidence": "high",
                    "reason_codes": ["rising_trend"],
                    "data_quality_flags": [],
                }
            ],
            confidence_summary={"overall": "high", "item_counts": {"high": 5}},
            data_quality_warnings=[],
            labels=["demo", "baseline"],
            annotation="A repeatable demo analysis for local testing.",
        )
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
