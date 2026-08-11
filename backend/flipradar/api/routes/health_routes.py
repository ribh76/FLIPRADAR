import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
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


class HealthCheck(BaseModel):
    status: str
    latency_ms: int | None = None


class HealthResponse(BaseModel):
    status: str
    service: str
    timestamp: datetime
    checks: dict[str, HealthCheck]


async def _readiness_response(db: AsyncSession) -> HealthResponse:
    database = await health_service.database_health(db)
    status_value = "healthy" if database["status"] == "healthy" else "unhealthy"
    return HealthResponse(
        status=status_value,
        service="FlipRadar API",
        timestamp=datetime.now(UTC),
        checks={
            "application": HealthCheck(status="healthy"),
            "database": HealthCheck(**database),
        },
    )


def _unhealthy_health_response(response: HealthResponse) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=response.model_dump(mode="json"),
    )


# Reports process-level API health. It takes no inputs and returns a simple status payload.
@router.get("/health", response_model=HealthResponse)
async def health_check(
    db: AsyncSession = Depends(get_db_session),
) -> HealthResponse | JSONResponse:
    """Return a concise readiness summary for humans and deployment monitors."""
    response = await _readiness_response(db)
    if response.status != "healthy":
        return _unhealthy_health_response(response)
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


@router.get("/health/live", response_model=HealthResponse)
async def liveness_check() -> HealthResponse:
    """Return process liveness without touching downstream dependencies."""
    return HealthResponse(
        status="healthy",
        service="FlipRadar API",
        timestamp=datetime.now(UTC),
        checks={"application": HealthCheck(status="healthy")},
    )


@router.get("/health/ready", response_model=HealthResponse)
async def readiness_check(
    db: AsyncSession = Depends(get_db_session),
) -> HealthResponse | JSONResponse:
    """Return readiness after verifying required dependencies."""
    response = await _readiness_response(db)
    if response.status != "healthy":
        return _unhealthy_health_response(response)
    return response


# Checks database connectivity. It takes no body input and returns the DB connection status.
@router.get("/db-health", response_model=HealthResponse)
async def db_health_check(
    db: AsyncSession = Depends(get_db_session),
) -> HealthResponse | JSONResponse:
    """Return database connectivity status by executing a minimal SELECT."""
    response = await _readiness_response(db)
    if response.status != "healthy":
        return _unhealthy_health_response(response)
    return response
