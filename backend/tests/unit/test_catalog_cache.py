import asyncio
from types import SimpleNamespace

import pytest

from flipradar.services import set_catalog_service


@pytest.mark.asyncio
async def test_catalog_hydration_coalesces_concurrent_provider_misses(monkeypatch):
    set_catalog_service.catalog_service._hydration_locks.clear()
    provider_calls = 0
    hydrated = False
    lego_set = SimpleNamespace(
        set_number="75192",
        name="Millennium Falcon",
        theme="Star Wars",
        release_year=2017,
        piece_count=7541,
    )

    async def list_sets(_db, **_kwargs):
        return [lego_set] if hydrated else []

    async def upsert(_db, _payload):
        nonlocal hydrated
        await asyncio.sleep(0.01)
        hydrated = True
        return lego_set

    def fetch_metadata(_set_number, _provider):
        nonlocal provider_calls
        provider_calls += 1
        return (
            {
                "set_number": "75192",
                "name": "Millennium Falcon",
                "theme": "Star Wars",
                "release_year": 2017,
                "piece_count": 7541,
            },
            "https://example.test/75192",
        )

    monkeypatch.setattr(set_catalog_service, "list_lego_sets", list_sets)
    monkeypatch.setattr(set_catalog_service, "upsert_lego_set", upsert)
    monkeypatch.setattr(set_catalog_service, "_provider_metadata", fetch_metadata)

    results = await asyncio.gather(
        *(
            set_catalog_service.search_lego_sets(
                object(), "75192", provider="bricklink"
            )
            for _ in range(8)
        )
    )

    assert provider_calls == 1
    assert sum(result["source"] == "provider" for result in results) == 1
    assert all(result["results"][0] is lego_set for result in results)
