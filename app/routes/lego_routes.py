import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db_session
from app.schemas import LegoSetCreate, LegoSetResponse
from models import LegoSet

router = APIRouter(tags=["lego sets"])
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
    result = await db.execute(select(LegoSet).where(LegoSet.set_number == set_number))
    return result.scalar_one_or_none()


async def _list_lego_sets(db: AsyncSession) -> list[LegoSet]:
    result = await db.execute(select(LegoSet).order_by(LegoSet.set_number))
    return list(result.scalars())


# Creates a LEGO set. It accepts set metadata and returns the persisted LEGO set row.
@router.post(
    "/sets", response_model=LegoSetResponse, status_code=status.HTTP_201_CREATED
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
@router.get("/set/{set_number}", response_model=LegoSetResponse)
async def get_lego_set(
    set_number: str, db: AsyncSession = Depends(get_db_session)
) -> LegoSet:
    """Fetch one LEGO set by set number."""
    logger.info("request started route=get_lego_set set_number=%s", set_number)
    lego_set = await _get_lego_set(db, set_number)
    if lego_set is None:
        logger.warning(
            "major validation failure route=get_lego_set set_number=%s", set_number
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="LEGO set not found"
        )
    logger.info("request finished route=get_lego_set set_number=%s", set_number)
    return lego_set


# Lists LEGO sets. It takes no body input and returns all stored LEGO set metadata.
@router.get("/sets", response_model=list[LegoSetResponse])
async def list_lego_sets(
    db: AsyncSession = Depends(get_db_session),
) -> list[LegoSet]:
    """List all LEGO set records ordered by set number."""
    logger.info("request started route=list_lego_sets")
    lego_sets = await _list_lego_sets(db)
    logger.info("request finished route=list_lego_sets")
    return lego_sets
