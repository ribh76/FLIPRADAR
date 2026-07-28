from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.core.settings import get_settings
from flipradar.database.repositories import delete_price_snapshots_before


async def prune_expired_price_snapshots(db: AsyncSession) -> int:
    """Delete metric snapshots older than the configured retention window."""
    cutoff = datetime.now(UTC) - timedelta(days=get_settings().pricing_retention_days)
    return await delete_price_snapshots_before(db, cutoff)
