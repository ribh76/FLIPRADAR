from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def check_database_connection(db: AsyncSession) -> dict[str, str]:
    await db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}
