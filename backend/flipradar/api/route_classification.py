"""Route visibility classifications and production access policy."""

from enum import StrEnum
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.routing import APIRoute

from flipradar.core.settings import AppEnvironment


class RouteClassification(StrEnum):
    """The operational audience for an HTTP endpoint."""

    PUBLIC = "public"
    INTERNAL = "internal"
    DEVELOPMENT = "development"
    DEBUG = "debug"
    ADMINISTRATIVE = "administrative"
    REFRESH = "refresh"
    SEED = "seed"
    MAINTENANCE = "maintenance"


_CLASSIFICATION_KEY = "x-route-classification"
_PRODUCTION_EXCLUDED = frozenset(RouteClassification) - {
    RouteClassification.PUBLIC,
}


def route_metadata(
    classification: RouteClassification, description: str
) -> dict[str, Any]:
    """Return FastAPI decorator options with a visible, machine-readable label."""
    return {
        "description": f"[{classification.value.upper()}] {description}",
        "openapi_extra": {_CLASSIFICATION_KEY: classification.value},
        "dependencies": [Depends(enforce_route_visibility)],
    }


def get_route_classification(route: APIRoute) -> RouteClassification:
    """Read a route's classification, treating legacy routes as public."""
    value = (route.openapi_extra or {}).get(_CLASSIFICATION_KEY)
    return RouteClassification(value) if value else RouteClassification.PUBLIC


def enforce_route_visibility(request: Request) -> None:
    """Make operational routes indistinguishable from absent routes in production."""
    route = request.scope.get("route")
    if (
        request.app.state.settings.application.environment
        is AppEnvironment.PRODUCTION
        and isinstance(route, APIRoute)
        and get_route_classification(route) in _PRODUCTION_EXCLUDED
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )


def apply_production_route_policy(app: FastAPI, environment: AppEnvironment) -> None:
    """Hide non-public operational routes from production OpenAPI documentation."""
    if environment is not AppEnvironment.PRODUCTION:
        return

    original_openapi = app.openapi

    def production_openapi() -> dict[str, Any]:
        schema = original_openapi()
        for path, operations in list(schema["paths"].items()):
            for method, operation in list(operations.items()):
                if (
                    isinstance(operation, dict)
                    and operation.get(_CLASSIFICATION_KEY)
                    in {item.value for item in _PRODUCTION_EXCLUDED}
                ):
                    del operations[method]
            if not operations:
                del schema["paths"][path]
        return schema

    app.openapi = production_openapi  # type: ignore[method-assign]
