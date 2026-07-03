from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import get_settings

constraint_naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=constraint_naming_convention)


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
    from models import (  # noqa: F401
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
