import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.dependencies.database import get_db_session
from flipradar.api.route_classification import RouteClassification, route_metadata
from flipradar.api.schemas import (
    ListingAnalysisResponse,
    ListingCollectionResponse,
    ListingCreate,
    ListingEvaluationRequest,
    ListingResponse,
)
from flipradar.api.schemas.common_schema import collection_response
from flipradar.domain.models import MarketplaceListing
from flipradar.services import listing_evaluation_service, listing_service
from flipradar.services.errors import ServiceError

router = APIRouter(tags=["Marketplace/Internal"])
logger = logging.getLogger(__name__)


# Creates a marketplace listing. It accepts a set number plus listing fields and returns the stored listing.
@router.post(
    "/listings",
    response_model=ListingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create marketplace listing",
    **route_metadata(RouteClassification.INTERNAL, "Store a marketplace listing."),
)
async def create_marketplace_listing(
    payload: ListingCreate, db: AsyncSession = Depends(get_db_session)
) -> MarketplaceListing:
    """Create one marketplace listing linked to an existing LEGO set."""
    logger.info(
        "request started route=create_marketplace_listing set_number=%s marketplace=%s",
        payload.set_number,
        payload.marketplace_name,
    )
    try:
        listing = await listing_service.create_listing(db, payload)
    except ServiceError as exc:
        logger.warning(
            "major validation failure route=create_marketplace_listing set_number=%s marketplace=%s",
            payload.set_number,
            payload.marketplace_name,
        )
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    logger.info(
        "request finished route=create_marketplace_listing set_number=%s marketplace=%s",
        payload.set_number,
        payload.marketplace_name,
    )
    return listing


@router.post(
    "/listing-evaluations",
    response_model=ListingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Evaluate a marketplace listing URL",
    description="Safely retrieves an eBay or BrickLink listing through its official API; a manual fallback may be supplied when retrieval fails.",
)
async def evaluate_listing_url(
    payload: ListingEvaluationRequest, db: AsyncSession = Depends(get_db_session)
) -> MarketplaceListing:
    """Ingest one allowlisted listing URL, recording whether data is provider verified."""
    logger.info(
        "request started route=evaluate_listing_url set_number=%s", payload.set_number
    )
    try:
        listing = await listing_evaluation_service.evaluate_listing_url(db, payload)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    logger.info(
        "request finished route=evaluate_listing_url set_number=%s", payload.set_number
    )
    return listing


@router.post(
    "/listings/{listing_id}/analysis",
    response_model=ListingAnalysisResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Analyze one marketplace listing",
)
async def analyze_marketplace_listing(
    listing_id: str, db: AsyncSession = Depends(get_db_session)
):
    from uuid import UUID

    from flipradar.services import listing_analysis_service

    try:
        evaluation = await listing_analysis_service.analyze_listing(
            db, UUID(listing_id)
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid listing ID",
        ) from exc
    if evaluation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found"
        )
    return evaluation


# Lists marketplace listings for a set. It accepts a set number path parameter and returns matching listings.
@router.get(
    "/listings/{set_number}",
    response_model=ListingCollectionResponse,
    summary="List set listings",
    description="Supporting backend data route for listings tied to a LEGO set number.",
)
async def list_marketplace_listings(
    set_number: str,
    db: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    condition: str | None = Query(default=None),
    listing_status: str | None = Query(default=None),
    marketplace_name: str | None = Query(default=None),
    order: str = Query(default="last_seen_desc"),
) -> dict:
    """List marketplace listings for one LEGO set number."""
    logger.info(
        "request started route=list_marketplace_listings set_number=%s", set_number
    )
    listings = await listing_service.list_listings_for_set(
        db,
        set_number,
        limit=limit + 1,
        offset=offset,
        condition=condition,
        listing_status=listing_status,
        marketplace_name=marketplace_name,
        order=order,
    )
    logger.info(
        "request finished route=list_marketplace_listings set_number=%s", set_number
    )
    return collection_response(listings, limit=limit, offset=offset)


# Compatibility listing route. It accepts a set number and returns listing data for that set.
@router.get(
    "/sets/{set_number}/listings",
    response_model=ListingCollectionResponse,
    summary="List set listings by set path",
    description="Supporting backend data route for listings tied to a LEGO set number.",
)
async def list_marketplace_listings_by_set_path(
    set_number: str,
    db: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    condition: str | None = Query(default=None),
    listing_status: str | None = Query(default=None),
    marketplace_name: str | None = Query(default=None),
    order: str = Query(default="last_seen_desc"),
) -> dict:
    """List marketplace listings using a set-oriented path."""
    logger.info(
        "request started route=list_marketplace_listings_by_set_path set_number=%s",
        set_number,
    )
    listings = await listing_service.list_listings_for_set(
        db,
        set_number,
        limit=limit + 1,
        offset=offset,
        condition=condition,
        listing_status=listing_status,
        marketplace_name=marketplace_name,
        order=order,
    )
    logger.info(
        "request finished route=list_marketplace_listings_by_set_path set_number=%s",
        set_number,
    )
    return collection_response(listings, limit=limit, offset=offset)


# Fetches the latest listing for a set. It accepts a set number and returns the newest listing by last_seen_at.
@router.get(
    "/listings/{set_number}/latest",
    response_model=ListingResponse,
    summary="Get latest listing",
    **route_metadata(RouteClassification.INTERNAL, "Fetch the newest stored listing."),
)
async def get_latest_marketplace_listing(
    set_number: str, db: AsyncSession = Depends(get_db_session)
) -> MarketplaceListing:
    """Fetch the latest marketplace listing for one LEGO set number."""
    logger.info(
        "request started route=get_latest_marketplace_listing set_number=%s",
        set_number,
    )
    listing = await listing_service.latest_listing_for_set(db, set_number)
    if listing is None:
        logger.warning(
            "major validation failure route=get_latest_marketplace_listing set_number=%s",
            set_number,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found"
        )
    logger.info(
        "request finished route=get_latest_marketplace_listing set_number=%s",
        set_number,
    )
    return listing
