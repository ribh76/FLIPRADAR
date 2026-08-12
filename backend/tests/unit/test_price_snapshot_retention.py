from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from flipradar.services import price_snapshot_retention


@pytest.mark.asyncio
async def test_prune_uses_configured_snapshot_retention_window(monkeypatch):
    captured = {}
    now = datetime.now(UTC)
    snapshot = SimpleNamespace(
        lego_set_id=uuid4(),
        marketplace_id=uuid4(),
        condition="new",
        currency="USD",
        metric_type="fair_market_value",
        retrieval_time=now - timedelta(days=31),
        created_at=now - timedelta(days=31),
        value=Decimal("100.00"),
        sample_size=4,
    )

    async def fake_snapshots(_db, cutoff):
        captured["cutoff"] = cutoff
        return [snapshot]

    rollups = []

    async def fake_upsert(_db, rollup):
        rollups.append(rollup)

    async def fake_delete(_db, _cutoff):
        return 3

    async def fake_flush():
        return None

    monkeypatch.setattr(
        price_snapshot_retention,
        "get_settings",
        lambda: SimpleNamespace(pricing_retention_days=30),
    )
    monkeypatch.setattr(
        price_snapshot_retention,
        "repositories",
        SimpleNamespace(
            get_price_snapshots_before=fake_snapshots,
            upsert_price_snapshot_rollup=fake_upsert,
            delete_price_snapshots_before=fake_delete,
        ),
    )

    assert (
        await price_snapshot_retention.prune_expired_price_snapshots(
            SimpleNamespace(flush=fake_flush)
        )
        == 3
    )
    assert {rollup["period"] for rollup in rollups} == {"weekly", "monthly"}
    assert (
        now - timedelta(days=30, seconds=1)
        < captured["cutoff"]
        < now - timedelta(days=30) + timedelta(seconds=1)
    )
