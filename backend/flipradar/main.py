import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from flipradar.api.error_handlers import register_exception_handlers
from flipradar.api.middleware import (
    RequestContextMiddleware,
    RollingWindowRateLimitMiddleware,
)
from flipradar.api.routes import (
    auth_routes,
    deal_routes,
    health_routes,
    inventory_routes,
    lego_routes,
    listing_routes,
    marketplace_routes,
    notification_routes,
    portfolio_routes,
    price_snapshot_routes,
    recommendation_routes,
    saved_search_routes,
    user_routes,
    watchlist_routes,
)
from flipradar.core.logging import setup_logging
from flipradar.core.observability import (
    configure_error_rate_alerting,
    configure_exception_monitoring,
)
from flipradar.core.settings import Settings, get_settings
from flipradar.core.startup import report_startup_configuration

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    logging_settings = resolved_settings.logging
    setup_logging(
        logging_settings.level,
        sqlalchemy_level=logging_settings.sqlalchemy_level,
        uvicorn_access_level=logging_settings.uvicorn_access_level,
        environment=resolved_settings.application.environment.value,
        release=resolved_settings.observability.release,
    )
    configure_exception_monitoring(
        dsn=resolved_settings.observability.sentry_dsn,
        environment=resolved_settings.application.environment.value,
        release=resolved_settings.observability.release,
    )
    configure_error_rate_alerting(
        threshold_percent=(
            resolved_settings.observability.error_rate_alert_threshold_percent
        ),
        minimum_requests=(
            resolved_settings.observability.error_rate_alert_minimum_requests
        ),
        window_seconds=resolved_settings.observability.error_rate_alert_window_seconds,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        report_startup_configuration(resolved_settings)
        yield

    app = FastAPI(
        title="FlipRadar API",
        version="1.0.0",
        description=(
            "FlipRadar V1 API for LEGO collectors: auth, set analysis, portfolio "
            "tracking, and set detail lookup."
        ),
        lifespan=lifespan,
        openapi_tags=[
            {
                "name": "Auth",
                "description": "Register, log in, and inspect the current user.",
            },
            {
                "name": "Analyze",
                "description": "Stored-snapshot recommendation analysis.",
            },
            {
                "name": "Portfolio",
                "description": "Authenticated portfolio tracking and valuation.",
            },
            {
                "name": "Users",
                "description": "Authenticated user profile routes.",
            },
            {"name": "Sets", "description": "LEGO set metadata and set detail lookup."},
            {
                "name": "Deals",
                "description": "Ranked eligible marketplace deal discovery.",
            },
            {
                "name": "Watchlist",
                "description": "Authenticated set and listing watchlist tracking.",
            },
            {"name": "Notifications", "description": "Watchlist notification inbox."},
            {
                "name": "Marketplace/Internal",
                "description": (
                    "Internal or development data refresh and snapshot helpers."
                ),
            },
            {"name": "system", "description": "Health checks."},
        ],
    )
    app.state.settings = resolved_settings

    app.add_middleware(
        RollingWindowRateLimitMiddleware,
        max_requests=5000,
        window_seconds=24 * 60 * 60,
    )
    app.add_middleware(RequestContextMiddleware)

    cors = resolved_settings.cors
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors.allowed_origins,
        allow_credentials=cors.allow_credentials,
        allow_methods=cors.allow_methods,
        allow_headers=cors.allow_headers,
    )

    app.include_router(health_routes.router)
    app.include_router(auth_routes.router)
    app.include_router(lego_routes.router)
    app.include_router(inventory_routes.router)
    app.include_router(deal_routes.router)
    app.include_router(saved_search_routes.router)
    app.include_router(watchlist_routes.router)
    app.include_router(notification_routes.router)
    app.include_router(listing_routes.router)
    app.include_router(price_snapshot_routes.router)
    app.include_router(recommendation_routes.router)
    app.include_router(portfolio_routes.router)
    app.include_router(user_routes.router)
    app.include_router(marketplace_routes.router)

    register_exception_handlers(app)

    logger.info("application configured")
    return app
