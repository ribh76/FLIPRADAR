"""Production endpoint authorization and operational-route access tests."""

from uuid import UUID

from fastapi.testclient import TestClient

from flipradar.api.route_classification import RouteClassification
from flipradar.core.settings import Settings
from flipradar.main import create_app


def production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "production",
        "app_debug": False,
        "jwt_secret_key": "a" * 48,
        "database_url_override": (
            "postgresql+asyncpg://app:strong-production-password@db.flipradar.example/flipradar"
        ),
        "database_password": "strong-production-password",
        "database_ssl_mode": "require",
        "cors_allowed_origins": "https://app.flipradar.example",
        "frontend_url": "https://app.flipradar.example",
        "redis_url": "rediss://redis.flipradar.example/0",
        "ebay_api_enabled": False,
        "bricklink_api_enabled": False,
    }
    values.update(overrides)
    return Settings.model_validate(values)


def _path_with_placeholder_values(path: str, operation: dict) -> str:
    for parameter in operation.get("parameters", []):
        if parameter.get("in") != "path":
            continue
        name = parameter["name"]
        schema = parameter.get("schema", {})
        value = (
            str(UUID(int=1))
            if schema.get("format") == "uuid" or name.endswith("_id")
            else "75192"
            if name == "set_number"
            else "1"
        )
        path = path.replace(f"{{{name}}}", value)
    return path


def test_production_hides_and_rejects_operational_routes():
    app = create_app(production_settings())
    schema = app.openapi()

    assert "/marketplace/update/{set_number}" not in schema["paths"]
    assert "post" not in schema["paths"]["/sets"]
    assert schema["paths"]["/inventory"]["get"]["x-route-classification"] == (
        RouteClassification.PUBLIC.value
    )
    operation_classifications = {
        operation.get("x-route-classification")
        for operations in schema["paths"].values()
        for operation in operations.values()
        if isinstance(operation, dict)
    }
    assert not (
        operation_classifications
        & {
            RouteClassification.INTERNAL.value,
            RouteClassification.DEVELOPMENT.value,
            RouteClassification.DEBUG.value,
            RouteClassification.ADMINISTRATIVE.value,
            RouteClassification.REFRESH.value,
            RouteClassification.SEED.value,
            RouteClassification.MAINTENANCE.value,
        }
    )

    with TestClient(app) as client:
        response = client.post("/marketplace/update/75192")

    assert response.status_code == 404


def test_every_bearer_protected_production_operation_rejects_anonymous_access():
    app = create_app(production_settings())
    schema = app.openapi()
    protected_operations = [
        (method.upper(), _path_with_placeholder_values(path, operation))
        for path, operations in schema["paths"].items()
        for method, operation in operations.items()
        if isinstance(operation, dict) and operation.get("security")
    ]

    assert protected_operations
    with TestClient(app) as client:
        for method, path in protected_operations:
            response = client.request(method, path)
            assert response.status_code == 401, f"{method} {path} is not protected"


def test_development_operational_routes_require_configured_basic_credentials():
    app = create_app(
        Settings.model_validate(
            {
                "app_env": "development",
                "operational_route_username": "operator",
                "operational_route_password": "local-operator-password",
            }
        )
    )

    with TestClient(app) as client:
        missing = client.post("/marketplace/update/75192")
        invalid = client.post(
            "/marketplace/update/75192", auth=("operator", "incorrect-password")
        )

    assert missing.status_code == 401
    assert missing.headers["www-authenticate"] == "Basic"
    assert invalid.status_code == 401
