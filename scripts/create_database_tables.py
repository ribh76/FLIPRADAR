import asyncio
import logging

from path_setup import ensure_backend_path

ensure_backend_path()

from flipradar.core.logging import setup_logging
from flipradar.database import check_database_connection, create_database_tables

logger = logging.getLogger(__name__)


async def main() -> None:
    setup_logging()
    await check_database_connection()
    await create_database_tables()
    logger.info("database tables created successfully")


if __name__ == "__main__":
    asyncio.run(main())
