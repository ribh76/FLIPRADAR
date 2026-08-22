from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from flipradar.core.settings import Settings
from flipradar.main import create_app


def release_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "staging",
        "app_debug": False,
        "app_release": "release-certification-20260822",
        "jwt_secret_key": "release-certification-secret-4X3q7Vb9N2mK8pL5rT1wY6dF0sHcJzA9vKe",
        "cors_allowed_origins": "https://staging.flipradar.example",
        "cors_allow_methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
        "cors_allow_headers": "Authorization,Content-Type,X-Request-ID",
        "ebay_api_enabled": False,
        "bricklink_api_enabled": False,
        "allow_mock_marketplace_providers": False,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"app_debug": True}, "APP_DEBUG must be false"),
        ({"app_release": "unknown"}, "APP_RELEASE must identify"),
        ({"cors_allowed_origins": "*"}, "CORS_ALLOWED_ORIGINS must be explicit"),
        (
            {"allow_mock_marketplace_providers": True},
            "ALLOW_MOCK_MARKETPLACE_PROVIDERS must be false",
        ),
    ],
)
def test_staging_rejects_release_unsafe_configuration(
    overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        release_settings(**overrides)


def test_api_lifespan_closes_runtime_connections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(release_settings())
    close_rate_limiter = AsyncMock()
    dispose_database_engine = AsyncMock()
    app.state.rate_limiter.close = close_rate_limiter
    monkeypatch.setattr("flipradar.main.dispose_engine", dispose_database_engine)

    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200

    close_rate_limiter.assert_awaited_once()
    dispose_database_engine.assert_awaited_once()
