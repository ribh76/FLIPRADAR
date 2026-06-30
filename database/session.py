import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from database.db import engine

logger = logging.getLogger(__name__)

SessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
    future=True,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    logger.debug("db session initiation")
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
            logger.debug("db session committed")
        except Exception:
            logger.exception("db session rollback after failure")
            await session.rollback()
            raise
        finally:
            logger.debug("db session closed")
