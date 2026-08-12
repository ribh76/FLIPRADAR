from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from flipradar.core.settings import DatabaseSettings, Settings, get_settings
from flipradar.database.base import Base

_engine: AsyncEngine | None = None


def _connect_args(database: DatabaseSettings) -> dict:
    connect_args = {}
    if database.ssl_mode == "disable":
        connect_args["ssl"] = False
    elif database.ssl_mode in {"require", "verify-ca", "verify-full"}:
        connect_args["ssl"] = True
    return connect_args


def create_database_engine(settings: Settings | None = None) -> AsyncEngine:
    resolved_settings = settings or get_settings()
    database = resolved_settings.database
    engine_kwargs = {
        "pool_pre_ping": True,
        "connect_args": _connect_args(database),
    }
    if not database.url.startswith("sqlite"):
        engine_kwargs["pool_size"] = database.pool_size
        engine_kwargs["max_overflow"] = database.max_overflow
    return create_async_engine(database.url, **engine_kwargs)


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_database_engine()
    return _engine


async def dispose_engine() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


async def create_database_tables(engine: AsyncEngine | None = None) -> None:
    from flipradar.domain.models import (  # noqa: F401
        Color,
        Element,
        LegoSet,
        ListingEvaluation,
        Marketplace,
        MarketplaceListing,
        Part,
        PartCategory,
        PortfolioItem,
        PriceSnapshot,
        PriceSnapshotRollup,
        Recommendation,
        User,
    )

    resolved_engine = engine or get_engine()
    async with resolved_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def check_database_connection(engine: AsyncEngine | None = None) -> bool:
    resolved_engine = engine or get_engine()
    async with resolved_engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    return True
