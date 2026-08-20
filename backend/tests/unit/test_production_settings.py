import pytest
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
    return Settings(**values)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"app_debug": True}, "APP_DEBUG must be false"),
        ({"jwt_secret_key": "change-me-" * 6}, "JWT_SECRET_KEY"),
        ({"database_ssl_mode": "prefer"}, "DATABASE_SSL_MODE"),
        (
            {"database_url_override": "postgresql+asyncpg://app:secret@localhost/db"},
            "localhost",
        ),
        (
            {
                "database_url_override": None,
                "database_host": "localhost",
                "database_password": "strong-production-password",
            },
            "localhost",
        ),
        ({"database_password": "flipradar_dev_password"}, "DATABASE_PASSWORD"),
        ({"database_url_override": "sqlite+aiosqlite:///:memory:"}, "DATABASE_URL"),
        (
            {
                "database_url_override": "postgresql://app:secret@db.example/db?sslmode=disable"
            },
            "DATABASE_URL must require SSL",
        ),
        ({"cors_allowed_origins": "*"}, "CORS_ALLOWED_ORIGINS"),
        ({"cors_allowed_origins": ""}, "CORS_ALLOWED_ORIGINS"),
        (
            {"cors_allowed_origins": "http://app.flipradar.example"},
            "CORS_ALLOWED_ORIGINS",
        ),
        ({"cors_allowed_origins": "https://localhost:5173"}, "localhost"),
        ({"frontend_url": "http://localhost:5173"}, "FRONTEND_URL"),
        ({"redis_url": "redis://localhost:6379/0"}, "REDIS_URL"),
        (
            {"alembic_database_url": "postgresql://app:secret@localhost/db"},
            "ALEMBIC_DATABASE_URL",
        ),
        (
            {
                "alembic_database_url": (
                    "postgresql://app:secret@db.example/db?sslmode=disable"
                )
            },
            "ALEMBIC_DATABASE_URL must require SSL",
        ),
        ({"celery_broker_url": "redis://localhost:6379/0"}, "CELERY_BROKER_URL"),
        (
            {"celery_result_backend": "redis://localhost:6379/0"},
            "CELERY_RESULT_BACKEND",
        ),
    ],
)
def test_production_rejects_unsafe_runtime_configuration(
    overrides: dict[str, object], message: str
):
    with pytest.raises(ValueError, match=message):
        production_settings(**overrides)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"ebay_api_enabled": True}, "eBay is enabled"),
        ({"bricklink_api_enabled": True}, "BrickLink is enabled"),
        ({"llm_enabled": True}, "LLM is enabled"),
        ({"email_enabled": True}, "Email is enabled"),
        (
            {
                "ebay_api_enabled": True,
                "ebay_api_key": "replace-with-client-id",
                "ebay_api_secret": "replace-with-client-secret",
            },
            "eBay must not use development credentials",
        ),
        (
            {
                "bricklink_api_enabled": True,
                "bricklink_consumer_key": "live-consumer-key",
                "bricklink_consumer_secret": "live-consumer-secret",
                "bricklink_token_value": "replace-with-token",
                "bricklink_token_secret": "live-token-secret",
            },
            "BrickLink must not use development credentials",
        ),
        (
            {
                "email_enabled": True,
                "auth_email_app_password": "replace-with-email-password",
            },
            "Email must not use development credentials",
        ),
        (
            {"llm_enabled": True, "anthropic_api_key": "replace-with-llm-key"},
            "LLM must not use development credentials",
        ),
    ],
)
def test_production_rejects_enabled_providers_without_safe_credentials(
    overrides: dict[str, object], message: str
):
    with pytest.raises(ValueError, match=message):
        production_settings(**overrides)


def test_valid_production_configuration_boots_successfully():
    settings = production_settings(
        ebay_api_enabled=True,
        ebay_api_key="live-client-id",
        ebay_api_secret="live-client-secret",
        bricklink_api_enabled=True,
        bricklink_consumer_key="live-consumer-key",
        bricklink_consumer_secret="live-consumer-secret",
        bricklink_token_value="live-token-value",
        bricklink_token_secret="live-token-secret",
        llm_enabled=True,
        anthropic_api_key="sk-ant-production-key",
        email_enabled=True,
        auth_email_app_password="mail-production-password",
    )

    with TestClient(create_app(settings)):
        pass


def test_production_excludes_internal_development_refresh_and_seed_routes():
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


def test_non_production_keeps_operational_routes_for_local_development():
    app = create_app(Settings(app_env="development"))
    schema = app.openapi()

    assert schema["paths"]["/marketplace/update/{set_number}"]["post"][
        "x-route-classification"
    ] == RouteClassification.REFRESH.value
    assert schema["paths"]["/sets"]["post"]["x-route-classification"] == (
        RouteClassification.SEED.value
    )
