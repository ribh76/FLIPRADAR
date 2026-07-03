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
    auth_routes,
    deal_routes,
    health_routes,
    lego_routes,
    marketplace_routes,
    pricing_routes,
    portfolio_routes,
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
    version="1.0.0",
    description=(
        "FlipRadar V1 API for LEGO collectors: auth, set analysis, portfolio "
        "tracking, and set detail lookup."
    ),
    openapi_tags=[
        {
            "name": "Auth",
            "description": "Register, log in, and inspect the current user.",
        },
        {"name": "Analyze", "description": "Stored-snapshot recommendation analysis."},
        {
            "name": "Portfolio",
            "description": "Authenticated portfolio tracking and valuation.",
        },
        {"name": "Sets", "description": "LEGO set metadata and set detail lookup."},
        {
            "name": "Marketplace/Internal",
            "description": "Internal or development data refresh and snapshot helpers.",
        },
        {"name": "system", "description": "Health checks."},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_routes.router)
app.include_router(auth_routes.router)
app.include_router(lego_routes.router)
app.include_router(deal_routes.router)
app.include_router(pricing_routes.router)
app.include_router(recommendation_routes.router)
app.include_router(portfolio_routes.router)
app.include_router(marketplace_routes.router)


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
