from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.core.settings import get_settings
from flipradar.database import repositories


async def aggregate_and_prune_portfolio_valuations(db: AsyncSession) -> int:
    """Roll old hourly history into daily points before removing raw records."""
    cutoff = datetime.now(UTC) - timedelta(
        days=get_settings().portfolio_valuation_retention_days
    )
    snapshots = await repositories.get_portfolio_snapshots_before(db, cutoff)
    latest_per_user_day = {}
    for snapshot in snapshots:
        key = (snapshot.user_id, snapshot.snapshot_at.date())
        latest_per_user_day.setdefault(key, snapshot)
    for snapshot in latest_per_user_day.values():
        await repositories.upsert_portfolio_daily_rollup(db, snapshot)
    await db.flush()
    return await repositories.delete_portfolio_snapshots_before(db, cutoff)
