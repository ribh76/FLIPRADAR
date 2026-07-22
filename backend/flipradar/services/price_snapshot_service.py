import logging

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.schemas import PriceSnapshotCreate
from flipradar.api.schemas.validation import MarketplaceName
from flipradar.api.schemas.validation import normalize_set_number
from flipradar.domain.models import LegoSet, Marketplace, PriceSnapshot

logger = logging.getLogger(__name__)


async def get_or_create_marketplace(
    db: AsyncSession, marketplace_name: str
) -> Marketplace:
    normalized_name = marketplace_name.lower()
    if normalized_name not in {marketplace.value for marketplace in MarketplaceName}:
        raise ValueError("Unsupported marketplace")
    result = await db.execute(
        select(Marketplace).where(Marketplace.name == normalized_name)
    )
    marketplace = result.scalar_one_or_none()
    if marketplace is not None:
        return marketplace

    marketplace = Marketplace(
        name=normalized_name,
        display_name=normalized_name.title(),
        fee_percent=0,
    )
    db.add(marketplace)
    await db.flush()
    return marketplace


async def create_price_snapshot(
    db: AsyncSession, payload: PriceSnapshotCreate
) -> PriceSnapshot:
    result = await db.execute(
        select(LegoSet).where(LegoSet.set_number == payload.set_number)
    )
    lego_set = result.scalar_one_or_none()
    if lego_set is None:
        raise LookupError("LEGO set not found")

    marketplace = await get_or_create_marketplace(db, payload.marketplace_name)
    snapshot_data = payload.model_dump(
        exclude={"set_number", "marketplace_name"}, exclude_none=True
    )
    snapshot = PriceSnapshot(
        lego_set_id=lego_set.id,
        marketplace_id=marketplace.id,
        **snapshot_data,
    )
    db.add(snapshot)
    await db.flush()
    await db.refresh(snapshot)
    return snapshot


async def list_price_snapshots_for_set(
    db: AsyncSession, set_number: str
) -> list[PriceSnapshot]:
    normalized_set_number = normalize_set_number(set_number)
    result = await db.execute(
        select(PriceSnapshot)
        .join(LegoSet)
        .where(LegoSet.set_number == normalized_set_number)
        .order_by(PriceSnapshot.snapshot_at.desc())
    )
    return list(result.scalars())


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
