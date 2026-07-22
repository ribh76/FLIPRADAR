import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.dependencies.database import get_db_session
from flipradar.services import health_service

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


# Checks database connectivity. It takes no body input and returns the DB connection status.
@router.get("/db-health")
async def db_health_check(
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Return database connectivity status by executing a minimal SELECT."""
    logger.info("request started route=db_health_check")
    response = await health_service.check_database_connection(db)
    logger.info("request finished route=db_health_check")
    return response
