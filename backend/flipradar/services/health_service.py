from time import perf_counter

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.core.observability import record_metric


async def check_database_connection(db: AsyncSession) -> dict[str, str]:
    started_at = perf_counter()
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        record_metric("database.health.check", tags={"outcome": "failure"})
        record_metric(
            "database.health.latency",
            (perf_counter() - started_at) * 1000,
            unit="ms",
            tags={"outcome": "failure"},
        )
        raise
    tags = {"outcome": "success"}
    record_metric("database.health.check", tags=tags)
    record_metric(
        "database.health.latency",
        (perf_counter() - started_at) * 1000,
        unit="ms",
        tags=tags,
    )
    return {"status": "ok", "database": "connected"}


async def database_health(db: AsyncSession) -> dict[str, int | str]:
    """Return a safe dependency status without leaking connection failures."""
    started_at = perf_counter()
    try:
        await check_database_connection(db)
    except Exception:
        return {
            "status": "unhealthy",
            "latency_ms": round((perf_counter() - started_at) * 1000),
        }
    return {
        "status": "healthy",
        "latency_ms": round((perf_counter() - started_at) * 1000),
    }
