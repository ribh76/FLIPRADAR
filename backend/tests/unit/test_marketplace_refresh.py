import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from flipradar.services import marketplace_service


@pytest.mark.asyncio
async def test_refresh_skips_snapshots_inside_freshness_window(monkeypatch):
    monkeypatch.setattr(
        marketplace_service.repositories,
        "latest_price_snapshot_retrieval_time",
        lambda _db, _set_number: _async(datetime.now(UTC) - timedelta(hours=1)),
    )
    monkeypatch.setattr(
        marketplace_service,
        "get_settings",
        lambda: SimpleNamespace(pricing_freshness_hours=24),
    )

    assert (
        await marketplace_service._refresh_marketplace_data(
            object(), "75192", force=False
        )
        is None
    )


@pytest.mark.asyncio
async def test_refresh_coalesces_concurrent_provider_cache_misses(monkeypatch):
    marketplace_service._refresh_locks.clear()
    provider_calls = 0
    refreshed_at: datetime | None = None

    async def latest(_db, _set_number):
        return refreshed_at

    async def update(_db, _set_number):
        nonlocal provider_calls, refreshed_at
        provider_calls += 1
        await asyncio.sleep(0.01)
        refreshed_at = datetime.now(UTC)
        return "fresh-snapshot"

    monkeypatch.setattr(
        marketplace_service.repositories, "latest_price_snapshot_retrieval_time", latest
    )
    monkeypatch.setattr(marketplace_service, "_update_marketplace_data", update)
    monkeypatch.setattr(
        marketplace_service,
        "get_settings",
        lambda: SimpleNamespace(pricing_freshness_hours=24),
    )

    results = await asyncio.gather(
        *(
            marketplace_service._refresh_marketplace_data(
                object(), "75192", force=False
            )
            for _ in range(8)
        )
    )

    assert provider_calls == 1
    assert results.count("fresh-snapshot") == 1
    assert results.count(None) == 7


@pytest.mark.asyncio
async def test_provider_timeout_keeps_successful_marketplace_results(monkeypatch):
    async def fetch(adapter, _set_number):
        if adapter.marketplace == "ebay":
            raise marketplace_service.ServiceProviderTimeoutError("timed out")
        return [{"marketplace": adapter.marketplace}]

    monkeypatch.setattr(marketplace_service, "_fetch_adapter_listings", fetch)
    monkeypatch.setattr(
        marketplace_service,
        "configured_marketplace_adapters",
        lambda: (
            _FixtureAdapter("ebay"),
            _FixtureAdapter("bricklink"),
        ),
    )

    listings, errors = await marketplace_service._fetch_marketplace_listings("75192")

    assert listings == [{"marketplace": "bricklink"}]
    assert errors == ["ebay"]


async def _async(value):
    return value


class _FixtureAdapter:
    def __init__(self, marketplace: str) -> None:
        self.marketplace = marketplace
