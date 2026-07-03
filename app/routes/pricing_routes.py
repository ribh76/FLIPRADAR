import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db_session
from app.schemas import PriceSnapshotCreate, PriceSnapshotResponse
from models import LegoSet, Marketplace, PriceSnapshot
from services.pricing_service import get_latest_price_snapshot_by_set_number

router = APIRouter(tags=["Marketplace/Internal"])
logger = logging.getLogger(__name__)


async def _get_or_create_marketplace(
    db: AsyncSession, marketplace_name: str
) -> Marketplace:
    normalized_name = marketplace_name.lower()
    result = await db.execute(
        select(Marketplace).where(Marketplace.name == normalized_name)
    )
    marketplace = result.scalar_one_or_none()
    if marketplace is not None:
        return marketplace

    marketplace = Marketplace(
        name=normalized_name,
        display_name=marketplace_name,
        fee_percent=0,
    )
    db.add(marketplace)
    await db.flush()
    return marketplace


async def _create_snapshot(
    db: AsyncSession, payload: PriceSnapshotCreate
) -> PriceSnapshot:
    result = await db.execute(
        select(LegoSet).where(LegoSet.set_number == payload.set_number)
    )
    lego_set = result.scalar_one_or_none()
    if lego_set is None:
        raise LookupError("LEGO set not found")

    marketplace = await _get_or_create_marketplace(db, payload.marketplace_name)
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


async def _list_snapshots_for_set(
    db: AsyncSession, set_number: str
) -> list[PriceSnapshot]:
    result = await db.execute(
        select(PriceSnapshot)
        .join(LegoSet)
        .where(LegoSet.set_number == set_number)
        .order_by(PriceSnapshot.snapshot_at.desc())
    )
    return list(result.scalars())


# Creates a price snapshot. It accepts a set number, marketplace, pricing bands, and returns the stored snapshot.
@router.post(
    "/snapshots",
    response_model=PriceSnapshotResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create price snapshot",
    description="Internal/development helper for storing a price snapshot.",
)
async def create_price_snapshot(
    payload: PriceSnapshotCreate, db: AsyncSession = Depends(get_db_session)
) -> PriceSnapshot:
    """Create one price snapshot linked to a LEGO set and marketplace."""
    logger.info(
        "request started route=create_price_snapshot set_number=%s marketplace=%s",
        payload.set_number,
        payload.marketplace_name,
    )
    try:
        snapshot = await _create_snapshot(db, payload)
    except LookupError as exc:
        logger.warning(
            "major validation failure route=create_price_snapshot set_number=%s marketplace=%s",
            payload.set_number,
            payload.marketplace_name,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    logger.info(
        "request finished route=create_price_snapshot set_number=%s marketplace=%s",
        payload.set_number,
        payload.marketplace_name,
    )
    return snapshot


# Lists snapshots for a set. It accepts a set number and returns historical snapshot rows.
@router.get(
    "/snapshots/{set_number}",
    response_model=list[PriceSnapshotResponse],
    summary="List price snapshots",
    description="Internal/development helper for listing stored snapshot history.",
)
async def list_price_snapshots(
    set_number: str, db: AsyncSession = Depends(get_db_session)
) -> list[PriceSnapshot]:
    """List all price snapshots for one LEGO set number."""
    logger.info("request started route=list_price_snapshots set_number=%s", set_number)
    snapshots = await _list_snapshots_for_set(db, set_number)
    logger.info(
        "request finished route=list_price_snapshots set_number=%s snapshot_count=%s",
        set_number,
        len(snapshots),
    )
    return snapshots


# Fetches the latest snapshot for a set. It accepts a set number and returns the newest pricing snapshot.
@router.get(
    "/snapshots/{set_number}/latest",
    response_model=PriceSnapshotResponse,
    summary="Get latest price snapshot",
    description="Internal/development helper for fetching the latest stored snapshot.",
)
async def get_latest_price_snapshot(
    set_number: str, db: AsyncSession = Depends(get_db_session)
) -> PriceSnapshot:
    """Fetch the latest price snapshot for one LEGO set number."""
    logger.info(
        "request started route=get_latest_price_snapshot set_number=%s", set_number
    )
    snapshot = await get_latest_price_snapshot_by_set_number(db, set_number)
    if snapshot is None:
        logger.warning(
            "major validation failure route=get_latest_price_snapshot set_number=%s snapshot_count=0",
            set_number,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found"
        )
    logger.info(
        "request finished route=get_latest_price_snapshot set_number=%s snapshot_count=1",
        set_number,
    )
    return snapshot
