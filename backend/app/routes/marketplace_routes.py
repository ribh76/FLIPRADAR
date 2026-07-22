import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import PriceSnapshotResponse
from database import get_db_session
from services import marketplace_service

router = APIRouter(prefix="/marketplace", tags=["Marketplace/Internal"])
logger = logging.getLogger(__name__)


@router.post(
    "/update/{set_number}",
    response_model=PriceSnapshotResponse,
    summary="Refresh marketplace data",
    description="Development/internal route that refreshes listings and builds a stored snapshot.",
)
async def update_marketplace_data(
    set_number: str, db: AsyncSession = Depends(get_db_session)
):
    logger.info(
        "request started route=update_marketplace_data set_number=%s", set_number
    )
    try:
        snapshot = await marketplace_service.update_marketplace_data(set_number, db)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    logger.info(
        "request finished route=update_marketplace_data set_number=%s", set_number
    )
    return snapshot
