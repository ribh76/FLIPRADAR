import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db_session
from app.schemas import ListingCreate, ListingResponse
from models import LegoSet, Marketplace, MarketplaceListing

router = APIRouter(tags=["marketplace listings"])
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


async def _create_listing(
    db: AsyncSession, payload: ListingCreate
) -> MarketplaceListing:
    result = await db.execute(
        select(LegoSet).where(LegoSet.set_number == payload.set_number)
    )
    lego_set = result.scalar_one_or_none()
    if lego_set is None:
        raise LookupError("LEGO set not found")

    marketplace = await _get_or_create_marketplace(db, payload.marketplace_name)
    listing_data = payload.model_dump(
        exclude={"set_number", "marketplace_name"}, mode="json"
    )
    listing = MarketplaceListing(
        lego_set_id=lego_set.id,
        marketplace_id=marketplace.id,
        **listing_data,
    )
    db.add(listing)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise ValueError("Marketplace listing already exists") from exc
    await db.refresh(listing)
    return listing


async def _list_listings_for_set(
    db: AsyncSession, set_number: str
) -> list[MarketplaceListing]:
    result = await db.execute(
        select(MarketplaceListing)
        .join(LegoSet)
        .where(LegoSet.set_number == set_number)
        .order_by(MarketplaceListing.last_seen_at.desc())
    )
    return list(result.scalars())


async def _latest_listing_for_set(
    db: AsyncSession, set_number: str
) -> MarketplaceListing | None:
    result = await db.execute(
        select(MarketplaceListing)
        .join(LegoSet)
        .where(LegoSet.set_number == set_number)
        .order_by(
            MarketplaceListing.last_seen_at.desc(), MarketplaceListing.created_at.desc()
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


# Creates a marketplace listing. It accepts a set number plus listing fields and returns the stored listing.
@router.post(
    "/listings",
    response_model=ListingResponse,
    status_code=status.HTTP_201_CREATED,
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
        listing = await _create_listing(db, payload)
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
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    logger.info(
        "request finished route=create_marketplace_listing set_number=%s marketplace=%s",
        payload.set_number,
        payload.marketplace_name,
    )
    return listing


# Lists marketplace listings for a set. It accepts a set number path parameter and returns matching listings.
@router.get("/listings/{set_number}", response_model=list[ListingResponse])
async def list_marketplace_listings(
    set_number: str, db: AsyncSession = Depends(get_db_session)
) -> list[MarketplaceListing]:
    """List marketplace listings for one LEGO set number."""
    logger.info(
        "request started route=list_marketplace_listings set_number=%s", set_number
    )
    listings = await _list_listings_for_set(db, set_number)
    logger.info(
        "request finished route=list_marketplace_listings set_number=%s", set_number
    )
    return listings


# Compatibility listing route. It accepts a set number and returns listing data for that set.
@router.get("/sets/{set_number}/listings", response_model=list[ListingResponse])
async def list_marketplace_listings_by_set_path(
    set_number: str, db: AsyncSession = Depends(get_db_session)
) -> list[MarketplaceListing]:
    """List marketplace listings using a set-oriented path."""
    logger.info(
        "request started route=list_marketplace_listings_by_set_path set_number=%s",
        set_number,
    )
    listings = await _list_listings_for_set(db, set_number)
    logger.info(
        "request finished route=list_marketplace_listings_by_set_path set_number=%s",
        set_number,
    )
    return listings


# Compatibility listing route. It accepts a set number and returns listing data for that set.
@router.get("/sets/{set_number}", response_model=list[ListingResponse])
async def list_marketplace_listings_by_exact_set_path(
    set_number: str, db: AsyncSession = Depends(get_db_session)
) -> list[MarketplaceListing]:
    """List marketplace listings using the exact set-oriented path from the API plan."""
    logger.info(
        "request started route=list_marketplace_listings_by_exact_set_path set_number=%s",
        set_number,
    )
    listings = await _list_listings_for_set(db, set_number)
    logger.info(
        "request finished route=list_marketplace_listings_by_exact_set_path set_number=%s",
        set_number,
    )
    return listings


# Fetches the latest listing for a set. It accepts a set number and returns the newest listing by last_seen_at.
@router.get("/listings/{set_number}/latest", response_model=ListingResponse)
async def get_latest_marketplace_listing(
    set_number: str, db: AsyncSession = Depends(get_db_session)
) -> MarketplaceListing:
    """Fetch the latest marketplace listing for one LEGO set number."""
    logger.info(
        "request started route=get_latest_marketplace_listing set_number=%s",
        set_number,
    )
    listing = await _latest_listing_for_set(db, set_number)
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
