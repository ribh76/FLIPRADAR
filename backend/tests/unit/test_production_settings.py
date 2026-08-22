from typing import Any

import pytest
from fastapi.testclient import TestClient

from flipradar.api.route_classification import RouteClassification
from flipradar.core.settings import Settings
from flipradar.main import create_app
from flipradar.services import auth_service


def production_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "app_env": "production",
        "app_debug": False,
        "app_release": "test-release-20260821",
        "allow_mock_marketplace_providers": False,
        "operational_route_username": None,
        "operational_route_password": None,
        "jwt_secret_key": "b5J9sN2vK7pR4xQ8mT1wY6dH3fL0cA9eG2iO5uI8rP1zX4qV7nC0kS3yB6jD9EeF",
        "database_url_override": (
            "postgresql+asyncpg://app:strong-production-password@db.flipradar.example/flipradar"
        ),
        "database_password": "strong-production-password",
        "database_ssl_mode": "require",
        "cors_allowed_origins": "https://app.flipradar.example",
        "cors_allow_methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
        "cors_allow_headers": "Authorization,Content-Type,X-Request-ID",
        "frontend_url": "https://app.flipradar.example",
        "redis_url": "rediss://default:redis-production-password@redis.flipradar.example/0",
        "celery_broker_url": None,
        "celery_result_backend": None,
        "ebay_api_enabled": False,
        "bricklink_api_enabled": False,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"app_debug": True}, "APP_DEBUG must be false"),
        ({"app_release": "unknown"}, "APP_RELEASE"),
        ({"operational_route_password": "should-not-exist"}, "Operational route"),
        ({"jwt_secret_key": "change-me-" * 6}, "JWT_SECRET_KEY"),
        ({"jwt_secret_key": "a" * 64}, "JWT_SECRET_KEY"),
        ({"database_ssl_mode": "prefer"}, "DATABASE_SSL_MODE"),
        (
            {"database_url_override": "postgresql+asyncpg://app:secret@localhost/db"},
            "localhost",
        ),
        (
            {"database_url_override": "postgresql+asyncpg://db.example/flipradar"},
            "DATABASE_URL must include external-provider credentials",
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
                "database_url_override": "postgresql://app:strong-password-value@db.example/db?sslmode=disable"
            },
            "DATABASE_URL must require SSL",
        ),
        (
            {
                "database_url_override": "postgresql://app:strong-password-value@db.example/db?sslmode=prefer"
            },
            "DATABASE_URL must require SSL",
        ),
        ({"cors_allowed_origins": "*"}, "CORS_ALLOWED_ORIGINS"),
        ({"cors_allowed_origins": ""}, "CORS_ALLOWED_ORIGINS"),
        ({"cors_allow_methods": "*"}, "CORS_ALLOW_METHODS"),
        ({"cors_allow_headers": "*"}, "CORS_ALLOW_HEADERS"),
        (
            {"cors_allowed_origins": "http://app.flipradar.example"},
            "CORS_ALLOWED_ORIGINS",
        ),
        ({"cors_allowed_origins": "https://localhost:5173"}, "localhost"),
        ({"frontend_url": "http://localhost:5173"}, "FRONTEND_URL"),
        ({"frontend_url": "https://staging.flipradar.example"}, "staging"),
        ({"frontend_url": "https://app.dev.flipradar.example"}, "development"),
        ({"redis_url": "redis://localhost:6379/0"}, "REDIS_URL"),
        ({"redis_url": "rediss://redis.flipradar.example/0"}, "REDIS_URL must include"),
        (
            {"alembic_database_url": "postgresql://app:secret@localhost/db"},
            "ALEMBIC_DATABASE_URL",
        ),
        (
            {
                "alembic_database_url": (
                    "postgresql://app:strong-password-value@db.example/db?sslmode=disable"
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


def test_production_transactional_email_urls_use_only_the_production_frontend(
    monkeypatch: pytest.MonkeyPatch,
):
    settings = production_settings()
    monkeypatch.setattr(auth_service, "get_settings", lambda: settings)

    urls = (
        auth_service._verification_url("verification-token"),
        auth_service._password_reset_url("reset-token"),
        auth_service._mfa_reset_url("mfa-reset-token"),
        auth_service._email_change_url("email-change-token"),
    )

    for url in urls:
        assert url.startswith("https://app.flipradar.example/")
        assert not any(
            marker in url.lower()
            for marker in ("localhost", "staging", "development", "dev")
        )


def test_non_production_keeps_operational_routes_for_local_development():
    app = create_app(Settings(app_env="development"))
    schema = app.openapi()

    assert (
        schema["paths"]["/marketplace/update/{set_number}"]["post"][
            "x-route-classification"
        ]
        == RouteClassification.REFRESH.value
    )
    assert schema["paths"]["/sets"]["post"]["x-route-classification"] == (
        RouteClassification.SEED.value
    )
