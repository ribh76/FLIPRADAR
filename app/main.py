import logging

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette import status
from starlette.requests import Request

from app.core.logging import setup_logging
from app.routes import (
    deal_routes,
    health_routes,
    lego_routes,
    pricing_routes,
    recommendation_routes,
)
from config import get_settings

settings = get_settings()
setup_logging(
    settings.log_level,
    sqlalchemy_level=settings.sqlalchemy_log_level,
    uvicorn_access_level=settings.uvicorn_access_log_level,
)
logger = logging.getLogger(__name__)
logger.info("application logging configured")

app = FastAPI(
    title="FlipRadar API",
    version="0.1.0",
    description="Backend API for LEGO resale market analysis and recommendations.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_routes.router)
app.include_router(lego_routes.router)
app.include_router(deal_routes.router)
app.include_router(pricing_routes.router)
app.include_router(recommendation_routes.router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    logger.warning(
        "major validation failure route=%s error_count=%s",
        request.url.path,
        len(exc.errors()),
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": jsonable_encoder(exc.errors())},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled request failure route=%s", request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )
