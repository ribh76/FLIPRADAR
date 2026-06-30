import logging
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models import LegoSet, PriceSnapshot, Recommendation

logger = logging.getLogger(__name__)


async def get_set_by_number(db: AsyncSession, set_number: str) -> LegoSet | None:
    try:
        result = await db.execute(
            select(LegoSet).where(LegoSet.set_number == str(set_number))
        )
        lego_set = result.scalar_one_or_none()
    except SQLAlchemyError:
        logger.exception(
            "unexpected DB failure while fetching set set_number=%s", set_number
        )
        raise
    if lego_set is None:
        logger.info("important missing data set not found set_number=%s", set_number)
    return lego_set


async def get_latest_snapshots_by_set_number(
    db: AsyncSession, set_number: str
) -> list[PriceSnapshot]:
    recent_snapshots = await get_recent_snapshots_by_set_number(
        db, set_number, limit=50
    )
    latest_by_marketplace = {}
    for snapshot in recent_snapshots:
        latest_by_marketplace.setdefault(snapshot.marketplace_id, snapshot)
    snapshots = list(latest_by_marketplace.values())
    if not snapshots:
        logger.info(
            "important missing data no snapshots set_number=%s snapshot_count=0",
            set_number,
        )
    return snapshots


async def get_recent_snapshots_by_set_number(
    db: AsyncSession, set_number: str, limit: int = 10
) -> list[PriceSnapshot]:
    statement = (
        select(PriceSnapshot)
        .options(selectinload(PriceSnapshot.marketplace))
        .join(LegoSet)
        .where(LegoSet.set_number == str(set_number))
        .order_by(PriceSnapshot.snapshot_at.desc(), PriceSnapshot.created_at.desc())
        .limit(limit)
    )
    try:
        result = await db.execute(statement)
    except SQLAlchemyError:
        logger.exception(
            "unexpected DB failure while fetching snapshots set_number=%s", set_number
        )
        raise
    return list(result.scalars())


async def create_recommendation(
    db: AsyncSession, recommendation_data: dict[str, Any]
) -> Recommendation:
    recommendation = Recommendation(**recommendation_data)
    db.add(recommendation)
    try:
        await db.flush()
        await db.refresh(recommendation)
    except SQLAlchemyError:
        logger.exception("unexpected DB failure while creating recommendation")
        raise
    return recommendation
