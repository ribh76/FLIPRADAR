import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db_session

router = APIRouter(tags=["system"])
logger = logging.getLogger(__name__)


# Reports process-level API health. It takes no inputs and returns a simple status payload.
@router.get("/health")
async def health_check() -> dict[str, str]:
    """Return API liveness status for load balancers and local smoke checks."""
    logger.info("request started route=health_check")
    response = {"status": "ok", "service": "FlipRadar API"}
    logger.info("request finished route=health_check")
    return response


async def _check_db(db: AsyncSession) -> dict[str, str]:
    await db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}


# Checks database connectivity. It takes no body input and returns the DB connection status.
@router.get("/db-health")
async def db_health_check(
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Return database connectivity status by executing a minimal SELECT."""
    logger.info("request started route=db_health_check")
    response = await _check_db(db)
    logger.info("request finished route=db_health_check")
    return response
