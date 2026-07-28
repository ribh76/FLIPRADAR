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


async def _async(value):
    return value
