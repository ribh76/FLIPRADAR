import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.dependencies.database import get_db_session
from flipradar.api.schemas import (
    LegoSetCreate,
    LegoSetResponse,
    PriceSnapshotResponse,
    SetDetailResponse,
)
from flipradar.domain.models import LegoSet
from flipradar.services import set_catalog_service, set_detail_service
from flipradar.services.price_snapshot_service import (
    get_latest_price_snapshot_by_set_number,
)

router = APIRouter(tags=["Sets"])
logger = logging.getLogger(__name__)


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
        lego_set = await set_catalog_service.create_lego_set(db, payload)
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
    lego_sets = await set_catalog_service.list_lego_sets(db)
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
    return PriceSnapshotResponse.model_validate(snapshot)
