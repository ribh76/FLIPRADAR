from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from flipradar.database.base import Base
from flipradar.core.settings import get_settings

settings = get_settings()

connect_args = {}
if settings.database_ssl_mode == "disable":
    connect_args["ssl"] = False
elif settings.database_ssl_mode in {"require", "verify-ca", "verify-full"}:
    connect_args["ssl"] = True

engine = create_async_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
)


async def create_database_tables() -> None:
    from flipradar.domain.models import (  # noqa: F401
        LegoSet,
        Marketplace,
        MarketplaceListing,
        PortfolioItem,
        PriceSnapshot,
        Recommendation,
        User,
    )

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def check_database_connection() -> bool:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    return True
