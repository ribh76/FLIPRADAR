from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from flipradar.services import price_snapshot_retention


@pytest.mark.asyncio
async def test_prune_uses_configured_snapshot_retention_window(monkeypatch):
    captured = {}
    now = datetime.now(UTC)

    async def fake_delete(_db, cutoff):
        captured["cutoff"] = cutoff
        return 3

    monkeypatch.setattr(
        price_snapshot_retention,
        "get_settings",
        lambda: SimpleNamespace(pricing_retention_days=30),
    )
    monkeypatch.setattr(
        price_snapshot_retention, "delete_price_snapshots_before", fake_delete
    )

    assert await price_snapshot_retention.prune_expired_price_snapshots(object()) == 3
    assert (
        now - timedelta(days=30, seconds=1)
        < captured["cutoff"]
        < now - timedelta(days=30) + timedelta(seconds=1)
    )
