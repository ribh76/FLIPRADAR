import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.dependencies.database import get_db_session
from flipradar.api.schemas import DealCollectionResponse
from flipradar.services import deal_finder_service

router = APIRouter(tags=["Deals"])
logger = logging.getLogger(__name__)


@router.get(
    "/deals",
    response_model=DealCollectionResponse,
    summary="Find ranked marketplace deals",
    description=(
        "Ranks eligible, recent active listings from a bounded default catalog "
        "universe. Expired, duplicate, mismatched, and low-confidence listings "
        "are excluded. Set refresh=true to refresh marketplace data first."
    ),
)
async def list_deals(
    db: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    universe_size: int = Query(
        default=deal_finder_service.DEFAULT_UNIVERSE_SIZE,
        ge=1,
        le=deal_finder_service.MAX_UNIVERSE_SIZE,
    ),
    refresh: bool = Query(default=False),
) -> dict:
    """Return a stable, offset-paginated page of ranked deal candidates."""
    logger.info(
        "request started route=list_deals universe_size=%s refresh=%s",
        universe_size,
        refresh,
    )
    result = await deal_finder_service.find_deals(
        db, universe_size=universe_size, refresh=refresh
    )
    page = result.deals[offset : offset + limit + 1]
    has_more = len(page) > limit
    logger.info(
        "request finished route=list_deals eligible_count=%s", len(result.deals)
    )
    return {
        "data": page[:limit],
        "pagination": {
            "limit": limit,
            "offset": offset,
            "count": min(len(page), limit),
            "has_more": has_more,
        },
        "refresh": result.refresh,
    }
