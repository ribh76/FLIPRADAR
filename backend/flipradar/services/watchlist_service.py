from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.schemas.portfolio_schema import PortfolioItemCreate
from flipradar.api.schemas.watchlist_schema import (
    WatchlistItemCreate,
    WatchlistItemUpdate,
    WatchlistMoveToPortfolio,
)
from flipradar.database import repositories
from flipradar.database.repositories import DuplicateRecordError, Pagination
from flipradar.domain.engines import price_estimator
from flipradar.domain.models import WatchlistItem
from flipradar.services import marketplace_service, portfolio_service
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
    return await _responses(db, items)


async def get_watchlist_item(db: AsyncSession, user_id: UUID, item_id: UUID) -> dict:
    return (await _responses(db, [await _owned_item(db, user_id, item_id)]))[0]


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
        item = await repositories.create_watchlist_item(db, data)
        return (await _responses(db, [item]))[0]
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
    return (await _responses(db, [updated]))[0]


async def delete_watchlist_item(db: AsyncSession, user_id: UUID, item_id: UUID) -> None:
    await repositories.delete_watchlist_item(
        db, await _owned_item(db, user_id, item_id)
    )


async def refresh_watchlist_items(db: AsyncSession, user_id: UUID) -> list[dict]:
    """Force fresh marketplace evidence for every watched set and listing."""
    items = await repositories.list_watchlist_items_for_user(db, user_id)
    set_numbers = {
        (item.lego_set or item.listing.lego_set).set_number
        for item in items
        if item.lego_set or item.listing
    }
    for set_number in set_numbers:
        try:
            await marketplace_service.refresh_marketplace_data(
                set_number, force=True, db=db
            )
        except Exception:
            # Preserve the last known evidence when a provider is unavailable.
            continue
    refreshed = await repositories.list_watchlist_items_for_user(db, user_id)
    now = datetime.now(UTC)
    for item in refreshed:
        if item.listing:
            item.last_known_listing_price = item.listing.total_price
            item.last_known_listing_status = item.listing.listing_status
        item.updated_at = now
    await db.flush()
    return await _responses(db, refreshed, checked_at=now)


async def move_watchlist_item_to_portfolio(
    db: AsyncSession,
    user_id: UUID,
    item_id: UUID,
    payload: WatchlistMoveToPortfolio,
) -> dict:
    item = await _owned_item(db, user_id, item_id)
    lego_set = item.lego_set or (item.listing.lego_set if item.listing else None)
    if lego_set is None:
        raise ServiceNotFoundError("Watchlist set not found")
    if item.last_known_listing_status in {"ended", "removed", "sold"}:
        raise ServiceConflictError("This listing is no longer available to purchase")
    purchase_price = payload.purchase_price or (
        item.listing.total_price if item.listing else None
    )
    if purchase_price is None:
        raise ServiceConflictError("Enter a purchase price before moving this set")
    condition = item.listing.condition if item.listing else "unknown"
    portfolio_item = await portfolio_service.add_item_to_portfolio(
        db,
        user_id,
        PortfolioItemCreate(
            set_number=lego_set.set_number,
            quantity=payload.quantity,
            purchase_price=purchase_price,
            condition=condition,
            purchase_date=datetime.now(UTC),
            currency=item.listing.currency if item.listing else "USD",
            notes=item.notes,
        ),
    )
    await repositories.delete_watchlist_item(db, item)
    return portfolio_item


async def _owned_item(db: AsyncSession, user_id: UUID, item_id: UUID) -> WatchlistItem:
    item = await repositories.get_watchlist_item_for_user(db, item_id, user_id)
    if item is None:
        raise ServiceNotFoundError("Watchlist item not found")
    return item


async def _responses(
    db: AsyncSession, items: list[WatchlistItem], *, checked_at: datetime | None = None
) -> list[dict]:
    snapshots_by_set = await repositories.get_latest_snapshots_for_set_numbers(
        db,
        {
            (item.lego_set or item.listing.lego_set).set_number
            for item in items
            if item.lego_set or item.listing
        },
    )
    return [_response(item, snapshots_by_set, checked_at=checked_at) for item in items]


def _response(
    item: WatchlistItem, snapshots_by_set: dict, *, checked_at: datetime | None
) -> dict:
    lego_set = item.lego_set or (item.listing.lego_set if item.listing else None)
    if lego_set is None:  # pragma: no cover - guarded by target foreign keys
        raise RuntimeError("Watchlist item has no set")
    estimate = price_estimator.estimate_fair_value(
        snapshots_by_set.get(lego_set.set_number, [])
    )
    valuation = estimate.get("fair_value") if estimate.get("error") is None else None
    current_price = item.listing.total_price if item.listing else None
    discount_percent = None
    if current_price is not None and valuation not in (None, Decimal("0")):
        discount_percent = ((valuation - current_price) / valuation * 100).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
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
        "current_price": current_price,
        "valuation": valuation,
        "discount_percent": discount_percent,
        "last_checked_at": checked_at
        or (item.listing.last_seen_at if item.listing else item.updated_at),
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }
