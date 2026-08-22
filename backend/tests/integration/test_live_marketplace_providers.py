"""Adapter integration tests using provider-shaped HTTP responses, never the network."""

from types import SimpleNamespace
from typing import cast

import pytest
import requests

from flipradar.core.settings import MarketplaceApiSettings, ProviderSettings, Settings
from flipradar.integrations import ebay_client
from flipradar.integrations.ebay_client import EbayApiError, EbayMarketplaceAdapter
from flipradar.services import marketplace_service


class ProviderResponse:
    def __init__(self, payload: dict, *, error: Exception | None = None) -> None:
        self._payload = payload
        self._error = error
        self.text = "provider response"

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self._error:
            raise self._error


class EbaySession:
    def __init__(self, *, search_response: ProviderResponse) -> None:
        self.search_response = search_response
        self.token_calls = 0
        self.search_calls = 0

    def post(self, *_args, **_kwargs) -> ProviderResponse:
        self.token_calls += 1
        return ProviderResponse(
            {"access_token": "application-token", "expires_in": 3600}
        )

    def get(self, *_args, **_kwargs) -> ProviderResponse:
        self.search_calls += 1
        return self.search_response


def _provider_settings() -> MarketplaceApiSettings:
    return MarketplaceApiSettings(
        ebay=ProviderSettings(
            enabled=True,
            configured=True,
            timeout_seconds=1,
            api_key="client-id",
            api_secret="client-secret",
        ),
        bricklink=ProviderSettings(enabled=False, configured=False, timeout_seconds=1),
    )


def test_production_configuration_selects_only_registered_live_adapters():
    settings = Settings.model_validate(
        {
            "APP_ENV": "production",
            "APP_DEBUG": False,
            "APP_RELEASE": "test-release-20260822",
            "ALLOW_MOCK_MARKETPLACE_PROVIDERS": False,
            "OPERATIONAL_ROUTE_USERNAME": "",
            "OPERATIONAL_ROUTE_PASSWORD": "",
            "JWT_SECRET_KEY": "xY7zA9bC2dE4fG6hI8jK0lM3nO5pQ7rS9tU1vW2xY4zA6bC8dE0fG2hI4jK6lM8n",
            "DATABASE_URL": "postgresql+asyncpg://app:strong-production-password@db.flipradar.example/flipradar",
            "DATABASE_PASSWORD": "strong-production-password",
            "DATABASE_SSL_MODE": "require",
            "CORS_ALLOWED_ORIGINS": "https://app.flipradar.example",
            "CORS_ALLOW_METHODS": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
            "CORS_ALLOW_HEADERS": "Authorization,Content-Type,X-Request-ID",
            "FRONTEND_URL": "https://app.flipradar.example",
            "REDIS_URL": "rediss://:redis-production-password@redis.flipradar.example/0",
            "CELERY_BROKER_URL": "",
            "CELERY_RESULT_BACKEND": "",
            "EBAY_API_ENABLED": True,
            "EBAY_API_KEY": "client-id",
            "EBAY_API_SECRET": "client-secret",
            "BRICKLINK_API_ENABLED": False,
        }
    )

    adapters = marketplace_service.configured_marketplace_adapters(settings.marketplace)

    assert [adapter.marketplace for adapter in adapters] == ["ebay"]
    assert all("mock" not in type(adapter).__module__ for adapter in adapters)


def test_ebay_adapter_successfully_executes_oauth_and_live_search(monkeypatch):
    session = EbaySession(
        search_response=ProviderResponse(
            {
                "itemSummaries": [
                    {
                        "itemId": "v1|123|0",
                        "title": "LEGO 75192 Millennium Falcon",
                        "itemWebUrl": "https://www.ebay.com/itm/123",
                        "condition": "New",
                        "price": {"value": "799.99", "currency": "USD"},
                        "shippingOptions": [{"shippingCost": {"value": "0.00"}}],
                    }
                ]
            }
        )
    )
    monkeypatch.setattr(
        ebay_client,
        "get_settings",
        lambda: SimpleNamespace(
            marketplace=SimpleNamespace(ebay=_provider_settings().ebay)
        ),
    )

    listings = EbayMarketplaceAdapter(
        session=cast(requests.Session, session)
    ).fetch_listings("75192")

    assert session.token_calls == 1
    assert session.search_calls == 1
    assert listings[0]["marketplace"] == "ebay"
    assert listings[0]["external_listing_id"] == "v1|123|0"
    assert listings[0]["price"] == "799.99"


def test_ebay_adapter_surfaces_a_failed_live_search(monkeypatch):
    session = EbaySession(
        search_response=ProviderResponse(
            {}, error=requests.HTTPError("upstream unavailable")
        )
    )
    monkeypatch.setattr(
        ebay_client,
        "get_settings",
        lambda: SimpleNamespace(
            marketplace=SimpleNamespace(ebay=_provider_settings().ebay)
        ),
    )

    with pytest.raises(EbayApiError, match="search listings"):
        EbayMarketplaceAdapter(session=cast(requests.Session, session)).fetch_listings(
            "75192"
        )

    assert session.token_calls == 1
    assert session.search_calls == 1
