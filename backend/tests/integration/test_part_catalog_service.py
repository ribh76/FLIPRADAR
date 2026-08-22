import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from flipradar.database import Base
from flipradar.domain.models import Color, Element, Part, PartCategory
from flipradar.integrations import bricklink_client
from flipradar.services.part_catalog_service import PartCatalogService


def _catalog_records() -> list[dict]:
    return [
        {
            "source": {"name": "BrickLink catalog", "url": "https://example.test"},
            "category": {"id": "26", "name": "Bricks"},
            "color": {"id": "5", "name": "Red"},
            "part": {
                "part_num": "3001",
                "name": "Brick 2 x 4",
                "aliases": ["basic brick"],
                "variants": [{"identifier": "3001a"}, {"identifier": "3001b"}],
                "image_urls": ["https://example.test/3001-red.png"],
                "first_known_year": 1958,
                "market_price": "0.18",
                "market_price_currency": "USD",
            },
            "element": {
                "element_id": "300121",
                "name": "Brick 2 x 4 Red",
                "first_known_year": 1958,
            },
        },
        {
            "source": {"name": "BrickLink catalog", "url": "https://example.test"},
            "category": {"id": "26", "name": "Bricks"},
            "color": {"id": "1", "name": "White"},
            "part": {
                "part_num": "3001",
                "name": "Brick 2 x 4",
                "aliases": ["basic brick"],
                "variants": [{"identifier": "3001a"}, {"identifier": "3001b"}],
                "image_urls": ["https://example.test/3001-white.png"],
                "first_known_year": 1958,
                "market_price": "0.18",
                "market_price_currency": "USD",
            },
            "element": {
                "element_id": "300101",
                "name": "Brick 2 x 4 White",
                "first_known_year": 1958,
            },
        },
    ]


def _configure_catalog_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        type(bricklink_client.client), "configured", property(lambda _self: True)
    )
    monkeypatch.setattr(
        bricklink_client.client,
        "get_part_catalog_records",
        lambda _query: _catalog_records(),
    )


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def test_part_catalog_sync_merges_duplicate_parts_and_keeps_color_elements(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    _configure_catalog_provider(monkeypatch)
    service = PartCatalogService()

    first = await service.synchronize(db_session, "3001")
    second = await service.synchronize(db_session, "3001")

    assert len(first) == 1
    assert len(second) == 1
    parts = list((await db_session.execute(select(Part))).scalars())
    assert len(parts) == 1
    assert parts[0].canonical_identifier == "part:3001"
    assert {variant["identifier"] for variant in parts[0].mold_variants} == {
        "3001a",
        "3001b",
    }
    assert len(list((await db_session.execute(select(Element))).scalars())) == 2
    assert len(list((await db_session.execute(select(Color))).scalars())) == 2
    assert len(list((await db_session.execute(select(PartCategory))).scalars())) == 1
    assert "source_timestamp_missing" in parts[0].quality_flags

    result = await service.search(db_session, "3001")
    assert result["source"] == "local"
    assert result["results"][0].name == "Brick 2 x 4"


async def test_catalog_refresh_replaces_quality_flags_when_provider_data_improves(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    _configure_catalog_provider(monkeypatch)
    service = PartCatalogService()
    await service.synchronize(db_session, "3001")
    part = (await db_session.execute(select(Part))).scalar_one()
    part.quality_flags = ["missing_images"]
    await db_session.flush()

    await service.synchronize(db_session, "3001")

    refreshed = (await db_session.execute(select(Part))).scalar_one()
    assert refreshed.quality_flags == ["source_timestamp_missing"]


async def test_part_lookup_supports_exact_text_fuzzy_and_catalog_filters(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    _configure_catalog_provider(monkeypatch)
    service = PartCatalogService()
    await service.synchronize(db_session, "3001")

    exact = await service.search(db_session, "part:3001")
    alias = await service.search(db_session, "basic brick")
    fuzzy = await service.search(db_session, "brik 2 x 4")
    filtered = await service.search(
        db_session,
        "brick",
        color="Red",
        category="Bricks",
        year=1958,
    )
    outside_known_year = await service.search(db_session, "brick", year=1957)

    for result in (exact, alias, fuzzy, filtered):
        assert result["source"] == "local"
        assert [part.canonical_identifier for part in result["results"]] == [
            "part:3001"
        ]
    assert exact["results"][0].match_type == "exact_part_number"
    assert exact["results"][0].match_confidence == "exact"
    assert exact["results"][0].match_explanation == "Exact part number match."
    assert fuzzy["results"][0].match_type == "fuzzy"
    assert str(fuzzy["results"][0].market_price) == "0.18"
    assert outside_known_year["query"] == "brick"
    assert outside_known_year["source"] == "local"
    assert outside_known_year["results"] == []
    assert outside_known_year["pagination"] == {
        "limit": 25,
        "offset": 0,
        "count": 0,
        "has_more": False,
    }
