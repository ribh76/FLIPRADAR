import time
from typing import Any

import pytest

from flipradar.integrations.bricklink_mock_client import adapter as bricklink_adapter
from flipradar.integrations.ebay_mock_client import adapter as ebay_adapter
from flipradar.integrations.marketplace_adapter import MarketplaceAdapter
from flipradar.services import marketplace_service
from flipradar.services.errors import ServiceProviderError, ServiceProviderTimeoutError


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


@pytest.fixture(params=[ebay_adapter, bricklink_adapter])
def mocked_provider_adapter(request: pytest.FixtureRequest) -> MarketplaceAdapter:
    return request.param


def test_mocked_provider_adapters_satisfy_listing_contract(
    mocked_provider_adapter: MarketplaceAdapter,
):
    listings = mocked_provider_adapter.fetch_listings("42071")

    assert listings
    assert all(
        listing["marketplace"] == mocked_provider_adapter.marketplace
        for listing in listings
    )
    assert all("condition" in listing for listing in listings)
    assert all(
        "currency" in listing or "currency_code" in listing for listing in listings
    )
    assert all(
        "shipping" in listing or "shipping_price" in listing for listing in listings
    )


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
