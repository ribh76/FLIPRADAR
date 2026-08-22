import pytest

from flipradar.core.settings import MarketplaceApiSettings, ProviderSettings, Settings
from flipradar.integrations.marketplace_adapter import MarketplaceAdapter
from flipradar.main import create_app
from flipradar.services import marketplace_service


class MockMarketplaceAdapter(MarketplaceAdapter):
    marketplace = "ebay"
    is_mock_provider = True

    def fetch_listings(self, set_number: str) -> list[dict]:
        del set_number
        return []


def _production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "production",
        "app_debug": False,
        "app_release": "test-release-20260822",
        "allow_mock_marketplace_providers": False,
        "operational_route_username": "",
        "operational_route_password": "",
        "jwt_secret_key": "xY7zA9bC2dE4fG6hI8jK0lM3nO5pQ7rS9tU1vW2xY4zA6bC8dE0fG2hI4jK6lM8n",
        "database_url_override": "postgresql+asyncpg://app:strong-production-password@db.flipradar.example/flipradar",
        "database_password": "strong-production-password",
        "database_ssl_mode": "require",
        "cors_allowed_origins": "https://app.flipradar.example",
        "cors_allow_methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
        "cors_allow_headers": "Authorization,Content-Type,X-Request-ID",
        "frontend_url": "https://app.flipradar.example",
        "redis_url": "rediss://:redis-production-password@redis.flipradar.example/0",
        "celery_broker_url": "",
        "celery_result_backend": "",
        "ebay_api_enabled": False,
        "bricklink_api_enabled": False,
    }
    values.update(overrides)
    return Settings(**values)


def test_mock_marketplace_access_defaults_to_local_development_and_test_only(
    monkeypatch: pytest.MonkeyPatch,
):
    # Explicit None exercises the automatic default while shielding this test
    # from a CI-level ALLOW_MOCK_MARKETPLACE_PROVIDERS environment variable.
    monkeypatch.delenv("ALLOW_MOCK_MARKETPLACE_PROVIDERS", raising=False)

    assert (
        Settings(
            app_env="development", allow_mock_marketplace_providers=None
        ).allow_mock_marketplace_providers
        is True
    )
    assert (
        Settings(
            app_env="test", allow_mock_marketplace_providers=None
        ).allow_mock_marketplace_providers
        is True
    )
    assert (
        Settings(
            app_env="staging",
            app_debug=False,
            app_release="test-release-20260822",
            jwt_secret_key="xY7zA9bC2dE4fG6hI8jK0lM3nO5pQ7rS9tU1vW2xY4zA6bC8dE0fG2hI4jK6lM8n",
            cors_allowed_origins="https://staging.flipradar.example",
            cors_allow_methods="GET,POST,PUT,PATCH,DELETE,OPTIONS",
            cors_allow_headers="Authorization,Content-Type,X-Request-ID",
            allow_mock_marketplace_providers=None,
        ).allow_mock_marketplace_providers
        is False
    )


def test_production_rejects_enabled_mock_marketplace_access():
    with pytest.raises(
        ValueError, match="ALLOW_MOCK_MARKETPLACE_PROVIDERS must be false"
    ):
        _production_settings(allow_mock_marketplace_providers=True)


def test_production_settings_helper_allows_default_overrides():
    with pytest.raises(ValueError, match="APP_DEBUG must be false"):
        _production_settings(app_debug=True)


def test_non_local_provider_selection_filters_mock_adapters(monkeypatch):
    monkeypatch.setattr(
        marketplace_service,
        "_ADAPTERS_BY_MARKETPLACE",
        {"ebay": MockMarketplaceAdapter()},
    )
    marketplace = MarketplaceApiSettings(
        ebay=ProviderSettings(enabled=True, configured=True, timeout_seconds=1),
        bricklink=ProviderSettings(enabled=False, configured=False, timeout_seconds=1),
        allow_mock_providers=False,
    )

    assert marketplace_service.configured_marketplace_adapters(marketplace) == ()


def test_production_startup_rejects_registered_mock_marketplace_adapter(monkeypatch):
    monkeypatch.setattr(
        marketplace_service,
        "_ADAPTERS_BY_MARKETPLACE",
        {"ebay": MockMarketplaceAdapter()},
    )

    with pytest.raises(ValueError, match="Mock marketplace providers"):
        create_app(_production_settings())


def test_valid_production_configuration_can_create_the_application():
    app = create_app(_production_settings())

    assert app.state.settings.app_env == "production"
