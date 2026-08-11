import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.dependencies.database import get_db_session
from flipradar.core.observability import capture_exception, record_metric
from flipradar.services import health_service

router = APIRouter(tags=["system"])
logger = logging.getLogger(__name__)


class FrontendErrorReport(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=1000)
    stack: str | None = Field(default=None, max_length=8000)
    url: str = Field(min_length=1, max_length=2000)


class ReportedFrontendError(Exception):
    """A sanitized browser error forwarded to backend exception monitoring."""


# Reports process-level API health. It takes no inputs and returns a simple status payload.
@router.get("/health")
async def health_check() -> dict[str, str]:
    """Return API liveness status for load balancers and local smoke checks."""
    logger.info("request started route=health_check")
    response = {"status": "ok", "service": "FlipRadar API"}
    logger.info("request finished route=health_check")
    return response


@router.post("/client-errors", status_code=status.HTTP_202_ACCEPTED)
async def report_client_error(report: FrontendErrorReport) -> dict[str, str]:
    """Forward sanitized browser failures to the configured error monitor."""
    exc = ReportedFrontendError(f"{report.name}: {report.message}")
    capture_exception(
        exc,
        context={"url": report.url, "stack": report.stack or ""},
    )
    record_metric("frontend.error", tags={"error_type": report.name})
    logger.warning("frontend error reported error_type=%s url=%s", report.name, report.url)
    return {"status": "accepted"}


@router.get("/health/live")
async def liveness_check() -> dict[str, str]:
    """Return process liveness without touching downstream dependencies."""
    return {"status": "ok", "service": "FlipRadar API"}


@router.get("/health/ready")
async def readiness_check(
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Return readiness after verifying required dependencies."""
    try:
        await health_service.check_database_connection(db)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service is not ready",
        ) from exc
    return {"status": "ok", "database": "connected", "service": "ready"}


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
