import time
from typing import Any

import pytest

from flipradar.core.settings import MarketplaceApiSettings, ProviderSettings
from flipradar.integrations.bricklink_client import BricklinkMarketplaceAdapter
from flipradar.integrations.ebay_client import EbayMarketplaceAdapter
from flipradar.integrations.marketplace_adapter import MarketplaceAdapter
from flipradar.services import marketplace_service
from flipradar.services.errors import (
    ServiceProviderError,
    ServiceProviderTimeoutError,
    ServiceProviderUnavailableError,
)


class FixtureMarketplaceAdapter(MarketplaceAdapter):
    def __init__(self, marketplace: str, listings: list[dict[str, Any]]) -> None:
        self.marketplace = marketplace
        self._listings = listings

    def fetch_listings(self, set_number: str) -> list[dict[str, Any]]:
        del set_number
        return self._tag_marketplace(self._listings)


class FailingMarketplaceAdapter(MarketplaceAdapter):
    marketplace = "ebay"

    def __init__(self) -> None:
        self.calls = 0

    def fetch_listings(self, set_number: str) -> list[dict[str, Any]]:
        del set_number
        self.calls += 1
        raise RuntimeError("mock provider failure")


class SlowMarketplaceAdapter(MarketplaceAdapter):
    marketplace = "bricklink"

    def fetch_listings(self, set_number: str) -> list[dict[str, Any]]:
        del set_number
        time.sleep(0.05)
        return []


class FixtureBricklinkClient:
    def _set_id(self, set_number: str) -> str:
        return f"{set_number}-1"

    def get_price_guide(self, _item_type: str, _number: str, condition: str) -> dict:
        return {
            "currency_code": "USD",
            "price_detail": [{"unit_price": "99.99"}],
            "condition": condition,
        }


def _provider(*, usable: bool) -> ProviderSettings:
    return ProviderSettings(enabled=usable, configured=usable, timeout_seconds=10)


def test_live_provider_adapters_produce_normalizable_listing_contract():
    ebay_listing = EbayMarketplaceAdapter._listing(
        {
            "itemId": "v1|1|0",
            "title": "LEGO 42071",
            "itemWebUrl": "https://www.ebay.com/itm/1",
            "condition": "New",
            "price": {"value": "42.00", "currency": "USD"},
            "shippingOptions": [],
        }
    )
    bricklink_listing = BricklinkMarketplaceAdapter(
        FixtureBricklinkClient()
    ).fetch_listings("42071")[0]

    assert ebay_listing["external_listing_id"] == "v1|1|0"
    assert ebay_listing["currency"] == "USD"
    assert bricklink_listing["marketplace"] == "bricklink"
    assert bricklink_listing["condition"] == "N"


def test_marketplace_adapter_selection_uses_provider_configuration():
    adapters = marketplace_service.configured_marketplace_adapters(
        MarketplaceApiSettings(
            ebay=_provider(usable=True), bricklink=_provider(usable=False)
        )
    )

    assert [adapter.marketplace for adapter in adapters] == ["ebay"]


@pytest.mark.asyncio
async def test_marketplace_refresh_rejects_when_no_provider_is_available(monkeypatch):
    monkeypatch.setattr(
        marketplace_service, "configured_marketplace_adapters", lambda: ()
    )

    with pytest.raises(ServiceProviderUnavailableError):
        await marketplace_service._fetch_marketplace_listings("42071")


@pytest.mark.asyncio
async def test_provider_failure_retries_then_raises_reusable_error():
    adapter = FailingMarketplaceAdapter()

    with pytest.raises(ServiceProviderError):
        await marketplace_service._fetch_adapter_listings(
            adapter, "42071", max_attempts=2, timeout_seconds=0.1
        )

    assert adapter.calls == 2


@pytest.mark.asyncio
async def test_provider_timeout_raises_reusable_timeout_error():
    with pytest.raises(ServiceProviderTimeoutError):
        await marketplace_service._fetch_adapter_listings(
            SlowMarketplaceAdapter(), "42071", max_attempts=1, timeout_seconds=0.001
        )
