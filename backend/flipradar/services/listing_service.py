from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.schemas import ListingCreate
from flipradar.database import repositories
from flipradar.database.repositories import Pagination
from flipradar.domain.models import Marketplace, MarketplaceListing
from flipradar.services.errors import (
    ServiceConflictError,
    ServiceNotFoundError,
    ServiceValidationError,
)


async def get_or_create_marketplace(
    db: AsyncSession, marketplace_name: str
) -> Marketplace:
    try:
        return await repositories.get_or_create_marketplace(db, marketplace_name)
    except ValueError as exc:
        raise ServiceValidationError(str(exc)) from exc
    except repositories.DuplicateRecordError as exc:
        raise ServiceConflictError(str(exc)) from exc


async def create_listing(
    db: AsyncSession, payload: ListingCreate
) -> MarketplaceListing:
    lego_set = await repositories.get_set_by_number(db, payload.set_number)
    if lego_set is None:
        raise ServiceNotFoundError("LEGO set not found")

    marketplace = await get_or_create_marketplace(db, payload.marketplace_name)
    listing_data = payload.model_dump(
        exclude={"set_number", "marketplace_name"}, mode="json"
    )
    try:
        async with db.begin_nested():
            return await repositories.create_listing(
                db,
                lego_set_id=lego_set.id,
                marketplace_id=marketplace.id,
                listing_data=listing_data,
            )
    except repositories.DuplicateRecordError as exc:
        raise ServiceConflictError(str(exc)) from exc


async def list_listings_for_set(
    db: AsyncSession,
    set_number: str,
    *,
    limit: int = repositories.DEFAULT_PAGE_LIMIT,
    offset: int = 0,
    condition: str | None = None,
    listing_status: str | None = None,
    marketplace_name: str | None = None,
    order: str = "last_seen_desc",
) -> list[MarketplaceListing]:
    return await repositories.list_listings_for_set(
        db,
        set_number,
        pagination=Pagination(limit=limit, offset=offset),
        condition=condition,
        listing_status=listing_status,
        marketplace_name=marketplace_name,
        order=order,
    )


async def latest_listing_for_set(
    db: AsyncSession, set_number: str
) -> MarketplaceListing | None:
    return await repositories.latest_listing_for_set(db, set_number)
