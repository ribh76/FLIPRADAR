import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.dependencies.database import get_db_session
from flipradar.api.schemas import ListingCreate, ListingResponse
from flipradar.domain.models import MarketplaceListing
from flipradar.services import listing_service

router = APIRouter(tags=["Marketplace/Internal"])
logger = logging.getLogger(__name__)


# Creates a marketplace listing. It accepts a set number plus listing fields and returns the stored listing.
@router.post(
    "/listings",
    response_model=ListingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create marketplace listing",
    description="Internal/development helper for storing a marketplace listing.",
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
    except LookupError as exc:
        logger.warning(
            "major validation failure route=create_marketplace_listing set_number=%s marketplace=%s",
            payload.set_number,
            payload.marketplace_name,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ValueError as exc:
        logger.warning(
            "major validation failure route=create_marketplace_listing set_number=%s marketplace=%s",
            payload.set_number,
            payload.marketplace_name,
        )
        status_code = (
            status.HTTP_400_BAD_REQUEST
            if str(exc) == "Unsupported marketplace"
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    logger.info(
        "request finished route=create_marketplace_listing set_number=%s marketplace=%s",
        payload.set_number,
        payload.marketplace_name,
    )
    return listing


# Lists marketplace listings for a set. It accepts a set number path parameter and returns matching listings.
@router.get(
    "/listings/{set_number}",
    response_model=list[ListingResponse],
    summary="List set listings",
    description="Supporting backend data route for listings tied to a LEGO set number.",
)
async def list_marketplace_listings(
    set_number: str, db: AsyncSession = Depends(get_db_session)
) -> list[MarketplaceListing]:
    """List marketplace listings for one LEGO set number."""
    logger.info(
        "request started route=list_marketplace_listings set_number=%s", set_number
    )
    listings = await listing_service.list_listings_for_set(db, set_number)
    logger.info(
        "request finished route=list_marketplace_listings set_number=%s", set_number
    )
    return listings


# Compatibility listing route. It accepts a set number and returns listing data for that set.
@router.get(
    "/sets/{set_number}/listings",
    response_model=list[ListingResponse],
    summary="List set listings by set path",
    description="Supporting backend data route for listings tied to a LEGO set number.",
)
async def list_marketplace_listings_by_set_path(
    set_number: str, db: AsyncSession = Depends(get_db_session)
) -> list[MarketplaceListing]:
    """List marketplace listings using a set-oriented path."""
    logger.info(
        "request started route=list_marketplace_listings_by_set_path set_number=%s",
        set_number,
    )
    listings = await listing_service.list_listings_for_set(db, set_number)
    logger.info(
        "request finished route=list_marketplace_listings_by_set_path set_number=%s",
        set_number,
    )
    return listings


# Fetches the latest listing for a set. It accepts a set number and returns the newest listing by last_seen_at.
@router.get(
    "/listings/{set_number}/latest",
    response_model=ListingResponse,
    summary="Get latest listing",
    description="Internal/development helper for fetching the newest stored listing.",
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
