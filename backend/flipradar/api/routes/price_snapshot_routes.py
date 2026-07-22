import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.dependencies.database import get_db_session
from flipradar.api.schemas import PriceSnapshotCreate, PriceSnapshotResponse
from flipradar.domain.models import PriceSnapshot
from flipradar.services import price_snapshot_service

router = APIRouter(tags=["Marketplace/Internal"])
logger = logging.getLogger(__name__)


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
        snapshot = await price_snapshot_service.create_price_snapshot(db, payload)
    except LookupError as exc:
        logger.warning(
            "major validation failure route=create_price_snapshot set_number=%s marketplace=%s",
            payload.set_number,
            payload.marketplace_name,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ValueError as exc:
        logger.warning(
            "major validation failure route=create_price_snapshot set_number=%s marketplace=%s",
            payload.set_number,
            payload.marketplace_name,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
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
    snapshots = await price_snapshot_service.list_price_snapshots_for_set(
        db, set_number
    )
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
    snapshot = await price_snapshot_service.get_latest_price_snapshot_by_set_number(
        db, set_number
    )
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
