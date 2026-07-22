import asyncio
from decimal import Decimal

from sqlalchemy import select

from path_setup import ensure_backend_path

ensure_backend_path()

from flipradar.database import SessionLocal, create_database_tables
from flipradar.domain.models import LegoSet, Marketplace, PriceSnapshot

DEMO_SETS = [
    {
        "set_number": "42071",
        "name": "Extreme Adventure",
        "theme": "Technic",
        "subtheme": None,
        "release_year": 2018,
        "retirement_year": 2018,
        "piece_count": 2382,
        "minifig_count": 0,
        "fair_market_value": Decimal("310.00"),
        "low_price": Decimal("260.00"),
        "median_price": Decimal("305.00"),
        "high_price": Decimal("375.00"),
        "listing_count": 16,
    },
    {
        "set_number": "75192",
        "name": "Millennium Falcon",
        "theme": "Star Wars",
        "subtheme": "Ultimate Collector Series",
        "release_year": 2017,
        "retirement_year": None,
        "piece_count": 7541,
        "minifig_count": 8,
        "fair_market_value": Decimal("690.00"),
        "low_price": Decimal("615.00"),
        "median_price": Decimal("680.00"),
        "high_price": Decimal("780.00"),
        "listing_count": 28,
    },
    {
        "set_number": "75313",
        "name": "AT-AT",
        "theme": "Star Wars",
        "subtheme": "Ultimate Collector Series",
        "release_year": 2021,
        "retirement_year": None,
        "piece_count": 6785,
        "minifig_count": 9,
        "fair_market_value": Decimal("725.00"),
        "low_price": Decimal("650.00"),
        "median_price": Decimal("715.00"),
        "high_price": Decimal("825.00"),
        "listing_count": 21,
    },
]


async def _get_or_create_marketplace(session) -> Marketplace:
    result = await session.execute(
        select(Marketplace).where(Marketplace.name == "demo")
    )
    marketplace = result.scalar_one_or_none()
    if marketplace is not None:
        return marketplace

    marketplace = Marketplace(
        name="demo",
        display_name="Demo Market",
        base_url=None,
        fee_percent=Decimal("0.00"),
    )
    session.add(marketplace)
    await session.flush()
    return marketplace


async def seed() -> None:
    await create_database_tables()
    async with SessionLocal() as session:
        marketplace = await _get_or_create_marketplace(session)
        for payload in DEMO_SETS:
            result = await session.execute(
                select(LegoSet).where(LegoSet.set_number == payload["set_number"])
            )
            lego_set = result.scalar_one_or_none()
            if lego_set is None:
                lego_set = LegoSet(
                    set_number=payload["set_number"],
                    name=payload["name"],
                    theme=payload["theme"],
                    subtheme=payload["subtheme"],
                    release_year=payload["release_year"],
                    retirement_year=payload["retirement_year"],
                    piece_count=payload["piece_count"],
                    minifig_count=payload["minifig_count"],
                )
                session.add(lego_set)
                await session.flush()

            snapshot = PriceSnapshot(
                lego_set_id=lego_set.id,
                marketplace_id=marketplace.id,
                condition="new",
                currency="USD",
                low_price=payload["low_price"],
                median_price=payload["median_price"],
                average_price=payload["median_price"],
                high_price=payload["high_price"],
                fair_market_value=payload["fair_market_value"],
                listing_count=payload["listing_count"],
                source_payload={"source": "demo-seed"},
            )
            session.add(snapshot)
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
