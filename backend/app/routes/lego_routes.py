import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import (
    LegoSetCreate,
    LegoSetResponse,
    PriceSnapshotResponse,
    SetDetailResponse,
)
from app.schemas.validation import normalize_set_number
from database import get_db_session
from models import LegoSet
from services import set_detail_service
from services.pricing_service import get_latest_price_snapshot_by_set_number

router = APIRouter(tags=["Sets"])
logger = logging.getLogger(__name__)


async def _create_lego_set(db: AsyncSession, payload: LegoSetCreate) -> LegoSet:
    lego_set = LegoSet(**payload.model_dump())
    db.add(lego_set)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise ValueError("LEGO set already exists") from exc
    await db.refresh(lego_set)
    return lego_set


async def _get_lego_set(db: AsyncSession, set_number: str) -> LegoSet | None:
    normalized_set_number = normalize_set_number(set_number)
    result = await db.execute(
        select(LegoSet).where(LegoSet.set_number == normalized_set_number)
    )
    return result.scalar_one_or_none()


async def _list_lego_sets(db: AsyncSession) -> list[LegoSet]:
    result = await db.execute(select(LegoSet).order_by(LegoSet.set_number))
    return list(result.scalars())


# Creates a LEGO set. It accepts set metadata and returns the persisted LEGO set row.
@router.post(
    "/sets",
    response_model=LegoSetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create set metadata",
    description="Create a LEGO set metadata record for local development and test data.",
)
async def create_lego_set(
    payload: LegoSetCreate, db: AsyncSession = Depends(get_db_session)
) -> LegoSet:
    """Create one LEGO set record after validating set metadata."""
    logger.info(
        "request started route=create_lego_set set_number=%s", payload.set_number
    )
    try:
        lego_set = await _create_lego_set(db, payload)
    except ValueError as exc:
        logger.warning(
            "major validation failure route=create_lego_set set_number=%s",
            payload.set_number,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    logger.info(
        "request finished route=create_lego_set set_number=%s", payload.set_number
    )
    return lego_set


# Fetches one LEGO set. It accepts a set number in the path and returns matching metadata.
@router.get(
    "/set/{set_number}",
    response_model=SetDetailResponse,
    deprecated=True,
    summary="Deprecated set detail lookup",
    description="Deprecated compatibility route. Use GET /sets/{set_number}.",
)
async def get_lego_set(
    set_number: str, db: AsyncSession = Depends(get_db_session)
) -> dict:
    """Fetch one LEGO set by set number using the deprecated singular path."""
    logger.info("request started route=get_lego_set set_number=%s", set_number)
    lego_set = await set_detail_service.get_set_detail(db, set_number)
    logger.info("request finished route=get_lego_set set_number=%s", set_number)
    return lego_set


# Lists LEGO sets. It takes no body input and returns all stored LEGO set metadata.
@router.get(
    "/sets",
    response_model=list[LegoSetResponse],
    summary="List set metadata",
    description="List stored LEGO set metadata records. This does not return listings.",
)
async def list_lego_sets(
    db: AsyncSession = Depends(get_db_session),
) -> list[LegoSet]:
    """List all LEGO set records ordered by set number."""
    logger.info("request started route=list_lego_sets")
    lego_sets = await _list_lego_sets(db)
    logger.info("request finished route=list_lego_sets")
    return lego_sets


@router.get(
    "/sets/{set_number}",
    response_model=SetDetailResponse,
    summary="Look up set detail",
    description="Return LEGO set metadata plus the latest stored market valuation snapshot.",
)
async def get_set_detail(
    set_number: str, db: AsyncSession = Depends(get_db_session)
) -> dict:
    logger.info("request started route=get_set_detail set_number=%s", set_number)
    detail = await set_detail_service.get_set_detail(db, set_number)
    logger.info("request finished route=get_set_detail set_number=%s", set_number)
    return detail


@router.get(
    "/sets/{set_number}/snapshots/latest",
    response_model=PriceSnapshotResponse,
    summary="Get latest set snapshot",
    description="Return the latest stored price snapshot for one LEGO set.",
)
async def get_latest_set_snapshot(
    set_number: str, db: AsyncSession = Depends(get_db_session)
) -> PriceSnapshotResponse:
    snapshot = await get_latest_price_snapshot_by_set_number(db, set_number)
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No price snapshots found"
        )
    return snapshot
