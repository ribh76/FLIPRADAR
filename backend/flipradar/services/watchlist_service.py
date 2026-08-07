from datetime import UTC, datetime, timedelta
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
from flipradar.domain.engines import price_estimator, scoring_engine
from flipradar.domain.models import WatchlistItem
from flipradar.services import marketplace_service, portfolio_service
from flipradar.services.errors import ServiceConflictError, ServiceNotFoundError

MANUAL_REFRESH_COOLDOWN = timedelta(hours=1)
_last_manual_refresh_by_user: dict[UUID, datetime] = {}


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
        responses = await _responses(db, [item])
        await _record_intelligence(db, responses)
        return responses[0]
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
    now = datetime.now(UTC)
    previous_refresh = _last_manual_refresh_by_user.get(user_id)
    if (
        previous_refresh is not None
        and now - previous_refresh < MANUAL_REFRESH_COOLDOWN
    ):
        remaining = MANUAL_REFRESH_COOLDOWN - (now - previous_refresh)
        raise ServiceConflictError(
            f"Manual refresh is available in {max(1, int(remaining.total_seconds() // 60) + 1)} minutes"
        )
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
    for item in refreshed:
        if item.listing:
            item.last_known_listing_price = item.listing.total_price
            item.last_known_listing_status = item.listing.listing_status
        item.updated_at = now
    await db.flush()
    responses = await _responses(db, refreshed, checked_at=now)
    await _record_intelligence(db, responses, observed_at=now)
    _last_manual_refresh_by_user[user_id] = now
    return responses


async def capture_watchlist_intelligence(db: AsyncSession, user_id: UUID) -> list[dict]:
    """Persist post-provider price, valuation, status, and score observations."""
    items = await repositories.list_watchlist_items_for_user(db, user_id)
    now = datetime.now(UTC)
    for item in items:
        if item.listing:
            item.last_known_listing_price = item.listing.total_price
            item.last_known_listing_status = item.listing.listing_status
        item.updated_at = now
    await db.flush()
    responses = await _responses(db, items, checked_at=now)
    await _record_intelligence(db, responses, observed_at=now)
    return responses


async def get_watchlist_history(
    db: AsyncSession, user_id: UUID, item_id: UUID
) -> list[dict]:
    item = await _owned_item(db, user_id, item_id)
    history = await repositories.list_watchlist_price_history(db, [item.id])
    return [
        {
            "observed_at": point.observed_at,
            "listing_price": point.listing_price,
            "fair_value": point.fair_value,
            "deal_score": point.deal_score,
            "listing_status": point.listing_status,
        }
        for point in reversed(history)
    ]


async def find_replacements(
    db: AsyncSession, user_id: UUID, item_id: UUID
) -> list[dict]:
    item = await _owned_item(db, user_id, item_id)
    if item.last_known_listing_status not in {"ended", "removed", "sold"}:
        raise ServiceConflictError(
            "Replacement search is only available for inactive listings"
        )
    lego_set = item.listing.lego_set if item.listing else item.lego_set
    if lego_set is None:
        raise ServiceNotFoundError("Watchlist set not found")
    listings = await repositories.list_listings_for_set(
        db,
        lego_set.set_number,
        listing_status="active",
        pagination=Pagination(limit=10),
    )
    snapshots = await repositories.get_latest_snapshots_for_set_numbers(
        db, {lego_set.set_number}
    )
    valuation = price_estimator.estimate_fair_value(
        snapshots.get(lego_set.set_number, [])
    )
    fair_value = valuation.get("fair_value") if valuation.get("error") is None else None
    results = []
    for listing in listings:
        scored = scoring_engine.score_deal(
            asking_price=listing.price,
            shipping_price=listing.shipping_price,
            fair_value=fair_value,
            product_match_confidence_score=listing.match_confidence or 0,
            seller_trust_score=listing.seller_rating or 50,
            is_complete=listing.is_complete,
        )
        results.append(
            {
                "listing_id": listing.id,
                "title": listing.title,
                "url": listing.url,
                "total_price": listing.total_price,
                "currency": listing.currency,
                "fair_value": fair_value,
                "deal_score": scored["score"],
                "recommendation": _recommendation(scored["score"]),
            }
        )
    return sorted(results, key=lambda result: result["deal_score"] or -1, reverse=True)


async def get_watchlist_summary(db: AsyncSession, user_id: UUID) -> dict:
    entries = await list_watchlist_items(db, user_id)
    scores = [
        entry["deal_score"] for entry in entries if entry["deal_score"] is not None
    ]
    return {
        "total_entries": len(entries),
        "under_target_count": sum(entry["is_under_target"] for entry in entries),
        "price_changed_count": sum(
            entry["price_change"] is not None for entry in entries
        ),
        "ended_or_removed_count": sum(
            entry["last_known_listing_status"] in {"ended", "removed"}
            for entry in entries
        ),
        "scored_entries": len(scores),
        "average_deal_score": (
            (sum(scores, Decimal("0")) / len(scores)).quantize(Decimal("0.01"))
            if scores
            else None
        ),
    }


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
    history = await repositories.list_watchlist_price_history(
        db, [item.id for item in items]
    )
    by_item: dict[UUID, list] = {}
    for entry in history:
        by_item.setdefault(entry.watchlist_item_id, []).append(entry)
    return [
        _response(
            item, snapshots_by_set, by_item.get(item.id, []), checked_at=checked_at
        )
        for item in items
    ]


def _response(
    item: WatchlistItem,
    snapshots_by_set: dict,
    history: list,
    *,
    checked_at: datetime | None,
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
    deal_score = None
    if item.listing and current_price is not None:
        deal_score = scoring_engine.score_deal(
            asking_price=item.listing.price,
            shipping_price=item.listing.shipping_price,
            fair_value=valuation,
            product_match_confidence_score=item.listing.match_confidence or 0,
            seller_trust_score=item.listing.seller_rating or 50,
            is_complete=item.listing.is_complete,
        )["score"]
    comparison = (
        history[1]
        if history and history[0].listing_price == current_price and len(history) > 1
        else (history[0] if history else None)
    )
    price_change = (
        (current_price - comparison.listing_price).quantize(Decimal("0.01"))
        if comparison
        and current_price is not None
        and comparison.listing_price is not None
        and current_price != comparison.listing_price
        else None
    )
    is_under_target = bool(
        item.target_price is not None
        and current_price is not None
        and current_price <= item.target_price
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
        "deal_score": deal_score,
        "price_change": price_change,
        "is_under_target": is_under_target,
        "recommendation": _recommendation(deal_score),
        "last_checked_at": checked_at
        or (item.listing.last_seen_at if item.listing else item.updated_at),
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _recommendation(deal_score: int | Decimal | None) -> str:
    if deal_score is None:
        return "PASS"
    if deal_score >= 70:
        return "BUY"
    if deal_score >= 50:
        return "WATCH"
    return "PASS"


async def _record_intelligence(
    db: AsyncSession, responses: list[dict], *, observed_at: datetime | None = None
) -> None:
    timestamp = observed_at or datetime.now(UTC)
    for entry in responses:
        await repositories.create_watchlist_price_history(
            db,
            {
                "watchlist_item_id": entry["id"],
                "listing_price": entry["current_price"],
                "listing_status": entry["last_known_listing_status"],
                "fair_value": entry["valuation"],
                "discount_percent": entry["discount_percent"],
                "deal_score": entry["deal_score"],
                "is_under_target": entry["is_under_target"],
                "observed_at": timestamp,
            },
        )
