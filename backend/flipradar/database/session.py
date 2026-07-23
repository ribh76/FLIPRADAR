import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flipradar.database.connection import get_engine

logger = logging.getLogger(__name__)

_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine(),
            expire_on_commit=False,
            future=True,
        )
    return _session_factory


def reset_session_factory() -> None:
    global _session_factory
    _session_factory = None


def SessionLocal(*args, **kwargs) -> AsyncSession:
    return get_session_factory()(*args, **kwargs)


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    logger.debug("db session initiation")
    async with get_session_factory()() as session:
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
