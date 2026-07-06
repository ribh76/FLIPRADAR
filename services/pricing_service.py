import logging

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.validation import normalize_set_number
from models import LegoSet, PriceSnapshot

logger = logging.getLogger(__name__)


async def get_latest_price_snapshot_by_set_number(
    db: AsyncSession, set_number: str
) -> PriceSnapshot | None:
    normalized_set_number = normalize_set_number(set_number)
    statement = (
        select(PriceSnapshot)
        .join(LegoSet)
        .where(LegoSet.set_number == normalized_set_number)
        .order_by(PriceSnapshot.snapshot_at.desc(), PriceSnapshot.created_at.desc())
        .limit(1)
    )
    try:
        result = await db.execute(statement)
    except SQLAlchemyError:
        logger.exception(
            "unexpected DB failure while fetching latest snapshot set_number=%s",
            set_number,
        )
        raise
    snapshot = result.scalar_one_or_none()
    if snapshot is None:
        logger.info(
            "important missing data no latest snapshot set_number=%s", set_number
        )
    return snapshot
