from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.schemas.watchlist_schema import (
    WatchlistItemCreate,
    WatchlistItemUpdate,
)
from flipradar.database import repositories
from flipradar.database.repositories import DuplicateRecordError, Pagination
from flipradar.domain.models import WatchlistItem
from flipradar.services.errors import ServiceConflictError, ServiceNotFoundError


async def list_watchlist_items(
    db: AsyncSession,
    user_id: UUID,
    *,
    limit: int | None = None,
    offset: int = 0,
) -> list[dict]:
    pagination = Pagination(limit=limit, offset=offset) if limit is not None else None
    items = await repositories.list_watchlist_items_for_user(
        db, user_id, pagination=pagination
    )
    return [_response(item) for item in items]


async def get_watchlist_item(db: AsyncSession, user_id: UUID, item_id: UUID) -> dict:
    return _response(await _owned_item(db, user_id, item_id))


async def create_watchlist_item(
    db: AsyncSession, user_id: UUID, payload: WatchlistItemCreate
) -> dict:
    data = payload.model_dump(exclude_none=True)
    if payload.set_number is not None:
        lego_set = await repositories.get_set_by_number(db, payload.set_number)
        if lego_set is None:
            raise ServiceNotFoundError("LEGO set not found")
        data.pop("set_number")
        data["lego_set_id"] = lego_set.id
    else:
        listing = await repositories.get_listing_for_evaluation(db, payload.listing_id)
        if listing is None:
            raise ServiceNotFoundError("Marketplace listing not found")
        data.pop("listing_id")
        data.update(
            marketplace_listing_id=listing.id,
            last_known_listing_price=listing.total_price,
            last_known_listing_status=listing.listing_status,
        )
    data["user_id"] = user_id
    try:
        return _response(await repositories.create_watchlist_item(db, data))
    except DuplicateRecordError as exc:
        raise ServiceConflictError("This item is already on your watchlist") from exc


async def update_watchlist_item(
    db: AsyncSession,
    user_id: UUID,
    item_id: UUID,
    payload: WatchlistItemUpdate,
) -> dict:
    item = await _owned_item(db, user_id, item_id)
    try:
        updated = await repositories.update_watchlist_item(
            db, item, payload.model_dump(exclude_unset=True)
        )
    except DuplicateRecordError as exc:
        raise ServiceConflictError("This item is already on your watchlist") from exc
    return _response(updated)


async def delete_watchlist_item(db: AsyncSession, user_id: UUID, item_id: UUID) -> None:
    await repositories.delete_watchlist_item(
        db, await _owned_item(db, user_id, item_id)
    )


async def _owned_item(db: AsyncSession, user_id: UUID, item_id: UUID) -> WatchlistItem:
    item = await repositories.get_watchlist_item_for_user(db, item_id, user_id)
    if item is None:
        raise ServiceNotFoundError("Watchlist item not found")
    return item


def _response(item: WatchlistItem) -> dict:
    lego_set = item.lego_set or (item.listing.lego_set if item.listing else None)
    if lego_set is None:  # pragma: no cover - guarded by target foreign keys
        raise RuntimeError("Watchlist item has no set")
    return {
        "id": item.id,
        "user_id": item.user_id,
        "entry_type": "listing" if item.marketplace_listing_id else "set",
        "set_number": lego_set.set_number,
        "listing_id": item.marketplace_listing_id,
        "target_price": item.target_price,
        "notes": item.notes,
        "saved_at": item.saved_at,
        "last_known_listing_price": item.last_known_listing_price,
        "last_known_listing_status": item.last_known_listing_status,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }
