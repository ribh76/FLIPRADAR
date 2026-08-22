from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.core.settings import get_settings
from flipradar.database import repositories


async def prune_expired_price_snapshots(db: AsyncSession) -> int:
    """Compact old observations into weekly/monthly history, then prune raw rows."""
    cutoff = datetime.now(UTC) - timedelta(days=get_settings().pricing_retention_days)
    snapshots = await repositories.get_price_snapshots_before(db, cutoff)
    for period in ("weekly", "monthly"):
        for rollup_data in _build_rollups(snapshots, period):
            await repositories.upsert_price_snapshot_rollup(db, rollup_data)
    await db.flush()
    return await repositories.delete_price_snapshots_before(db, cutoff)


def _period_start(observed_at: datetime, period: str) -> date:
    observed_date = (
        observed_at.replace(tzinfo=UTC).date()
        if observed_at.tzinfo is None
        else observed_at.astimezone(UTC).date()
    )
    if period == "weekly":
        return observed_date - timedelta(days=observed_date.weekday())
    return observed_date.replace(day=1)


def _build_rollups(snapshots: list, period: str) -> list[dict]:
    grouped: dict[tuple, list] = defaultdict(list)
    for snapshot in snapshots:
        key = (
            snapshot.lego_set_id,
            snapshot.marketplace_id,
            snapshot.condition,
            snapshot.currency,
            snapshot.metric_type,
            _period_start(snapshot.retrieval_time, period),
        )
        grouped[key].append(snapshot)

    rollups = []
    for key, observations in grouped.items():
        observations.sort(key=lambda item: (item.retrieval_time, item.created_at))
        values = [Decimal(item.value) for item in observations]
        sample_sizes = [item.sample_size for item in observations]
        rollups.append(
            {
                "lego_set_id": key[0],
                "marketplace_id": key[1],
                "condition": key[2],
                "currency": key[3],
                "metric_type": key[4],
                "period": period,
                "period_start": key[5],
                "average_value": (sum(values) / Decimal(len(values))).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                ),
                "low_value": min(values),
                "high_value": max(values),
                "latest_value": values[-1],
                "average_sample_size": int(
                    (Decimal(sum(sample_sizes)) / len(sample_sizes)).quantize(
                        Decimal("1"), rounding=ROUND_HALF_UP
                    )
                ),
                "observation_count": len(observations),
                "latest_retrieval_time": observations[-1].retrieval_time,
            }
        )
    return rollups
