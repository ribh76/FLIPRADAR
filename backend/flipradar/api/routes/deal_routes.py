import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
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
    min_budget: Decimal | None = Query(default=None, ge=0),
    max_budget: Decimal | None = Query(default=None, ge=0),
    theme: str | None = Query(default=None, min_length=1, max_length=120),
    subtheme: str | None = Query(default=None, min_length=1, max_length=120),
    min_release_year: int | None = Query(default=None, ge=1949, le=2100),
    max_release_year: int | None = Query(default=None, ge=1949, le=2100),
    min_age_years: int | None = Query(default=None, ge=0, le=100),
    max_age_years: int | None = Query(default=None, ge=0, le=100),
    condition: str | None = Query(default=None),
    retirement_status: str | None = Query(default=None),
    marketplace: str | None = Query(default=None),
    min_discount: Decimal | None = Query(default=None, ge=0, le=100),
    min_confidence: int | None = Query(default=None, ge=0, le=100),
    max_shipping: Decimal | None = Query(default=None, ge=0),
    order: str = Query(default="score_desc"),
) -> dict:
    """Return a stable, offset-paginated page of ranked deal candidates."""
    logger.info(
        "request started route=list_deals universe_size=%s refresh=%s",
        universe_size,
        refresh,
    )
    filters = deal_finder_service.DealFilters(
        min_budget=min_budget,
        max_budget=max_budget,
        theme=theme,
        subtheme=subtheme,
        min_release_year=min_release_year,
        max_release_year=max_release_year,
        min_age_years=min_age_years,
        max_age_years=max_age_years,
        condition=condition,
        retirement_status=retirement_status,
        marketplace=marketplace,
        min_discount=min_discount,
        min_confidence=min_confidence,
        max_shipping=max_shipping,
        order=order,
    )
    try:
        result = await deal_finder_service.find_deals(
            db, universe_size=universe_size, refresh=refresh, filters=filters
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
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
