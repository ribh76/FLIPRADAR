"""Route visibility classifications and production access policy."""

from enum import StrEnum
from secrets import compare_digest
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.routing import APIRoute
from fastapi.security import HTTPBasic, HTTPBasicCredentials

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
_operational_credentials = HTTPBasic(auto_error=False)


def route_metadata(
    classification: RouteClassification, description: str
) -> dict[str, Any]:
    """Return FastAPI decorator options with a visible, machine-readable label."""
    metadata: dict[str, Any] = {
        "description": f"[{classification.value.upper()}] {description}",
        "openapi_extra": {_CLASSIFICATION_KEY: classification.value},
    }
    if classification in _PRODUCTION_EXCLUDED:
        metadata["dependencies"] = [Depends(enforce_route_visibility)]
    return metadata


def get_route_classification(route: APIRoute) -> RouteClassification:
    """Read a route's classification, treating legacy routes as public."""
    value = (route.openapi_extra or {}).get(_CLASSIFICATION_KEY)
    return RouteClassification(value) if value else RouteClassification.PUBLIC


def enforce_route_visibility(
    request: Request,
    credentials: HTTPBasicCredentials | None = Depends(_operational_credentials),
) -> None:
    """Block production operational routes and protect them elsewhere."""
    route = request.scope.get("route")
    if not isinstance(route, APIRoute):
        return

    classification = get_route_classification(route)
    if classification not in _PRODUCTION_EXCLUDED:
        return

    settings = request.app.state.settings
    environment = settings.application.environment
    if environment is AppEnvironment.PRODUCTION:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )

    # Tests need direct fixture setup, but engineering and maintenance routes
    # must never be open in a developer or staging deployment.
    if environment is AppEnvironment.TEST:
        return

    expected = settings.operational_routes
    if (
        not expected.username
        or not expected.password
        or credentials is None
        or not compare_digest(credentials.username, expected.username)
        or not compare_digest(credentials.password, expected.password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Operational route credentials are required",
            headers={"WWW-Authenticate": "Basic"},
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
