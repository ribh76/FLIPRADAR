import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from flipradar.api.schemas.validation import MarketplaceName, normalize_set_number
from flipradar.domain.models import (
    LegoSet,
    Marketplace,
    MarketplaceListing,
    PortfolioItem,
    PriceSnapshot,
    Recommendation,
    RefreshTokenBlacklist,
    User,
)

logger = logging.getLogger(__name__)

DEFAULT_PAGE_LIMIT = 100
MAX_PAGE_LIMIT = 500


class RepositoryError(Exception):
    """Base class for expected repository failures."""


class DuplicateRecordError(RepositoryError):
    """Raised when a uniqueness constraint rejects a duplicate action."""


class ConflictRecordError(RepositoryError):
    """Raised when a write conflicts with current database state."""


class WatchlistRepositoryUnavailableError(RepositoryError):
    """Raised until a watchlist persistence model is added."""


@dataclass(frozen=True)
class Pagination:
    limit: int = DEFAULT_PAGE_LIMIT
    offset: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "limit", min(max(self.limit, 1), MAX_PAGE_LIMIT))
        object.__setattr__(self, "offset", max(self.offset, 0))


def page(limit: int = DEFAULT_PAGE_LIMIT, offset: int = 0) -> Pagination:
    return Pagination(limit=limit, offset=offset)


def _apply_pagination(statement, pagination: Pagination):
    return statement.limit(pagination.limit).offset(pagination.offset)


def _marketplace_base_url(marketplace_name: str) -> str | None:
    if marketplace_name == MarketplaceName.EBAY.value:
        return "https://www.ebay.com"
    if marketplace_name == MarketplaceName.BRICKLINK.value:
        return "https://www.bricklink.com"
    return None


def _normalize_marketplace(marketplace_name: str) -> str:
    normalized_name = marketplace_name.lower().strip()
    if normalized_name not in {marketplace.value for marketplace in MarketplaceName}:
        raise ValueError("Unsupported marketplace")
    return normalized_name


# User repository
async def get_user_by_username_or_email(
    db: AsyncSession, identifier: str
) -> User | None:
    normalized = identifier.strip().lower()
    result = await db.execute(
        select(User).where(or_(User.username == normalized, User.email == normalized))
    )
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, user_data: dict[str, Any]) -> User:
    user = User(**user_data)
    db.add(user)
    try:
        await db.flush()
        await db.refresh(user)
    except IntegrityError as exc:
        raise DuplicateRecordError("User already exists") from exc
    except SQLAlchemyError:
        logger.exception("unexpected DB failure while creating user")
        raise
    return user


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    return await db.get(User, user_id)


async def is_refresh_token_blacklisted(db: AsyncSession, token_hash: str) -> bool:
    result = await db.execute(
        select(RefreshTokenBlacklist.id).where(
            RefreshTokenBlacklist.token_hash == token_hash
        )
    )
    return result.scalar_one_or_none() is not None


async def blacklist_refresh_token(
    db: AsyncSession,
    *,
    user_id: UUID,
    token_hash: str,
    token_jti: str,
    expires_at: datetime,
    reason: str,
) -> RefreshTokenBlacklist:
    token = RefreshTokenBlacklist(
        user_id=user_id,
        token_hash=token_hash,
        token_jti=token_jti,
        expires_at=expires_at,
        reason=reason,
    )
    db.add(token)
    try:
        await db.flush()
        await db.refresh(token)
    except IntegrityError as exc:
        raise DuplicateRecordError("Refresh token already revoked") from exc
    return token


# Set repository
async def get_set_by_number(db: AsyncSession, set_number: str) -> LegoSet | None:
    normalized_set_number = normalize_set_number(set_number)
    try:
        result = await db.execute(
            select(LegoSet).where(LegoSet.set_number == normalized_set_number)
        )
        lego_set = result.scalar_one_or_none()
    except SQLAlchemyError:
        logger.exception(
            "unexpected DB failure while fetching set set_number=%s", set_number
        )
        raise
    if lego_set is None:
        logger.info("important missing data set not found set_number=%s", set_number)
    return lego_set


async def create_set(db: AsyncSession, set_data: dict[str, Any]) -> LegoSet:
    lego_set = LegoSet(**set_data)
    db.add(lego_set)
    try:
        await db.flush()
        await db.refresh(lego_set)
    except IntegrityError as exc:
        raise DuplicateRecordError("LEGO set already exists") from exc
    return lego_set


async def list_sets(
    db: AsyncSession,
    *,
    pagination: Pagination | None = None,
    theme: str | None = None,
    query: str | None = None,
    order: str = "set_number",
) -> list[LegoSet]:
    pagination = pagination or page()
    statement = select(LegoSet)
    if theme:
        statement = statement.where(func.lower(LegoSet.theme) == theme.strip().lower())
    if query:
        normalized_query = f"%{query.strip().lower()}%"
        statement = statement.where(
            or_(
                func.lower(LegoSet.set_number).like(normalized_query),
                func.lower(LegoSet.name).like(normalized_query),
            )
        )
    if order == "release_year_desc":
        statement = statement.order_by(LegoSet.release_year.desc().nullslast())
    elif order == "created_at_desc":
        statement = statement.order_by(LegoSet.created_at.desc())
    else:
        statement = statement.order_by(LegoSet.set_number.asc())
    result = await db.execute(_apply_pagination(statement, pagination))
    return list(result.scalars())


# Marketplace repository
async def get_marketplace_by_name(
    db: AsyncSession, marketplace_name: str
) -> Marketplace | None:
    normalized_name = _normalize_marketplace(marketplace_name)
    result = await db.execute(
        select(Marketplace).where(Marketplace.name == normalized_name)
    )
    return result.scalar_one_or_none()


async def get_or_create_marketplace(
    db: AsyncSession, marketplace_name: str
) -> Marketplace:
    normalized_name = _normalize_marketplace(marketplace_name)
    result = await db.execute(
        select(Marketplace).where(Marketplace.name == normalized_name)
    )
    marketplace = result.scalar_one_or_none()
    if marketplace is not None:
        return marketplace

    marketplace = Marketplace(
        name=normalized_name,
        display_name=normalized_name.title(),
        base_url=_marketplace_base_url(normalized_name),
        fee_percent=0,
    )
    db.add(marketplace)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise DuplicateRecordError("Marketplace already exists") from exc
    return marketplace


# Listing repository
async def get_existing_listing(
    db: AsyncSession, marketplace_id: UUID, external_listing_id: str
) -> MarketplaceListing | None:
    result = await db.execute(
        select(MarketplaceListing).where(
            MarketplaceListing.marketplace_id == marketplace_id,
            MarketplaceListing.external_listing_id == external_listing_id,
        )
    )
    return result.scalar_one_or_none()


async def create_listing(
    db: AsyncSession,
    *,
    lego_set_id: UUID,
    marketplace_id: UUID,
    listing_data: dict[str, Any],
) -> MarketplaceListing:
    listing = MarketplaceListing(
        lego_set_id=lego_set_id,
        marketplace_id=marketplace_id,
        **listing_data,
    )
    db.add(listing)
    try:
        await db.flush()
        await db.refresh(listing)
    except IntegrityError as exc:
        raise DuplicateRecordError("Marketplace listing already exists") from exc
    return listing


async def list_listings_for_set(
    db: AsyncSession,
    set_number: str,
    *,
    pagination: Pagination | None = None,
    condition: str | None = None,
    listing_status: str | None = None,
    marketplace_name: str | None = None,
    order: str = "last_seen_desc",
) -> list[MarketplaceListing]:
    pagination = pagination or page()
    normalized_set_number = normalize_set_number(set_number)
    statement = select(MarketplaceListing).join(LegoSet).join(Marketplace)
    statement = statement.where(LegoSet.set_number == normalized_set_number)
    if condition:
        statement = statement.where(MarketplaceListing.condition == condition)
    if listing_status:
        statement = statement.where(MarketplaceListing.listing_status == listing_status)
    if marketplace_name:
        statement = statement.where(
            Marketplace.name == _normalize_marketplace(marketplace_name)
        )
    if order == "price_asc":
        statement = statement.order_by(MarketplaceListing.total_price.asc())
    elif order == "price_desc":
        statement = statement.order_by(MarketplaceListing.total_price.desc())
    else:
        statement = statement.order_by(
            MarketplaceListing.last_seen_at.desc(),
            MarketplaceListing.created_at.desc(),
        )
    result = await db.execute(_apply_pagination(statement, pagination))
    return list(result.scalars())


async def latest_listing_for_set(
    db: AsyncSession, set_number: str
) -> MarketplaceListing | None:
    listings = await list_listings_for_set(
        db, set_number, pagination=Pagination(limit=1, offset=0)
    )
    return listings[0] if listings else None


async def bulk_create_marketplace_listings(
    db: AsyncSession,
    *,
    lego_set_id: UUID,
    marketplace_id: UUID,
    listings_data: list[dict[str, Any]],
    skip_duplicates: bool = True,
) -> list[MarketplaceListing]:
    if not listings_data:
        return []
    if skip_duplicates:
        external_ids = [item["external_listing_id"] for item in listings_data]
        result = await db.execute(
            select(MarketplaceListing.external_listing_id).where(
                MarketplaceListing.marketplace_id == marketplace_id,
                MarketplaceListing.external_listing_id.in_(external_ids),
            )
        )
        existing_ids = set(result.scalars())
        listings_data = [
            item
            for item in listings_data
            if item["external_listing_id"] not in existing_ids
        ]
    listings = [
        MarketplaceListing(
            lego_set_id=lego_set_id,
            marketplace_id=marketplace_id,
            **listing_data,
        )
        for listing_data in listings_data
    ]
    db.add_all(listings)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise DuplicateRecordError("Marketplace listing already exists") from exc
    return listings


# Price repository
async def create_price_snapshot(
    db: AsyncSession,
    *,
    lego_set_id: UUID,
    marketplace_id: UUID,
    snapshot_data: dict[str, Any],
) -> PriceSnapshot:
    snapshot = PriceSnapshot(
        lego_set_id=lego_set_id,
        marketplace_id=marketplace_id,
        **snapshot_data,
    )
    db.add(snapshot)
    try:
        await db.flush()
        await db.refresh(snapshot)
    except IntegrityError as exc:
        raise DuplicateRecordError("Price snapshot already exists") from exc
    return snapshot


async def bulk_create_price_snapshots(
    db: AsyncSession, snapshots_data: list[dict[str, Any]]
) -> list[PriceSnapshot]:
    snapshots = [PriceSnapshot(**snapshot_data) for snapshot_data in snapshots_data]
    db.add_all(snapshots)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise DuplicateRecordError("Price snapshot already exists") from exc
    return snapshots


async def list_price_snapshots_for_set(
    db: AsyncSession,
    set_number: str,
    *,
    pagination: Pagination | None = None,
    condition: str | None = None,
    marketplace_name: str | None = None,
    order: str = "snapshot_desc",
) -> list[PriceSnapshot]:
    pagination = pagination or page()
    normalized_set_number = normalize_set_number(set_number)
    statement = (
        select(PriceSnapshot)
        .options(selectinload(PriceSnapshot.marketplace))
        .join(LegoSet)
        .join(Marketplace)
        .where(LegoSet.set_number == normalized_set_number)
    )
    if condition:
        statement = statement.where(PriceSnapshot.condition == condition)
    if marketplace_name:
        statement = statement.where(
            Marketplace.name == _normalize_marketplace(marketplace_name)
        )
    if order == "created_at_desc":
        statement = statement.order_by(PriceSnapshot.created_at.desc())
    else:
        statement = statement.order_by(
            PriceSnapshot.snapshot_at.desc(), PriceSnapshot.created_at.desc()
        )
    result = await db.execute(_apply_pagination(statement, pagination))
    return list(result.scalars())


async def get_recent_snapshots_by_set_number(
    db: AsyncSession, set_number: str, limit: int = 10
) -> list[PriceSnapshot]:
    return await list_price_snapshots_for_set(
        db, set_number, pagination=Pagination(limit=limit, offset=0)
    )


async def get_latest_price_snapshot_by_set_number(
    db: AsyncSession, set_number: str
) -> PriceSnapshot | None:
    snapshots = await get_recent_snapshots_by_set_number(db, set_number, limit=1)
    snapshot = snapshots[0] if snapshots else None
    if snapshot is None:
        logger.info(
            "important missing data no latest snapshot set_number=%s", set_number
        )
    return snapshot


async def get_latest_snapshots_by_set_number(
    db: AsyncSession, set_number: str
) -> list[PriceSnapshot]:
    recent_snapshots = await get_recent_snapshots_by_set_number(
        db, set_number, limit=50
    )
    latest_by_marketplace = {}
    for snapshot in recent_snapshots:
        latest_by_marketplace.setdefault(snapshot.marketplace_id, snapshot)
    snapshots = list(latest_by_marketplace.values())
    if not snapshots:
        logger.info(
            "important missing data no snapshots set_number=%s snapshot_count=0",
            set_number,
        )
    return snapshots


async def get_latest_snapshots_for_set_numbers(
    db: AsyncSession, set_numbers: set[str]
) -> dict[str, list[PriceSnapshot]]:
    if not set_numbers:
        return {}
    normalized_set_numbers = {
        normalize_set_number(set_number) for set_number in set_numbers
    }
    result = await db.execute(
        select(PriceSnapshot)
        .options(
            selectinload(PriceSnapshot.marketplace),
            selectinload(PriceSnapshot.lego_set),
        )
        .join(LegoSet)
        .where(LegoSet.set_number.in_(normalized_set_numbers))
        .order_by(
            LegoSet.set_number.asc(),
            PriceSnapshot.snapshot_at.desc(),
            PriceSnapshot.created_at.desc(),
        )
    )
    latest_by_set_and_marketplace: dict[str, dict[UUID, PriceSnapshot]] = defaultdict(
        dict
    )
    for snapshot in result.scalars():
        set_number = snapshot.lego_set.set_number
        latest_by_set_and_marketplace[set_number].setdefault(
            snapshot.marketplace_id, snapshot
        )
    return {
        set_number: list(by_marketplace.values())
        for set_number, by_marketplace in latest_by_set_and_marketplace.items()
    }


# Portfolio repository
async def create_portfolio_item(
    db: AsyncSession, user_id: UUID, item_data: dict[str, Any]
) -> PortfolioItem:
    normalized_set_number = normalize_set_number(item_data["set_number"])
    lego_set = await get_set_by_number(db, normalized_set_number)
    if lego_set is None:
        raise ValueError("LEGO set not found")

    persisted_data = {
        key: value for key, value in item_data.items() if key != "set_number"
    }
    item = PortfolioItem(user_id=user_id, lego_set_id=lego_set.id, **persisted_data)
    db.add(item)
    try:
        await db.flush()
        await db.refresh(item)
        await db.refresh(item, attribute_names=["lego_set"])
    except IntegrityError as exc:
        raise ConflictRecordError("Invalid portfolio item") from exc
    except SQLAlchemyError:
        logger.exception("unexpected DB failure while creating portfolio item")
        raise
    return item


async def get_portfolio_items_for_user(
    db: AsyncSession,
    user_id: UUID,
    *,
    pagination: Pagination | None = None,
    condition: str | None = None,
    order: str = "created_at_desc",
) -> list[PortfolioItem]:
    pagination = pagination or page()
    statement = (
        select(PortfolioItem)
        .options(selectinload(PortfolioItem.lego_set))
        .where(PortfolioItem.user_id == user_id)
    )
    if condition:
        statement = statement.where(PortfolioItem.condition == condition)
    if order == "created_at_asc":
        statement = statement.order_by(PortfolioItem.created_at.asc())
    else:
        statement = statement.order_by(PortfolioItem.created_at.desc())
    result = await db.execute(_apply_pagination(statement, pagination))
    return list(result.scalars())


async def get_all_portfolio_items_for_user(
    db: AsyncSession, user_id: UUID
) -> list[PortfolioItem]:
    result = await db.execute(
        select(PortfolioItem)
        .options(selectinload(PortfolioItem.lego_set))
        .where(PortfolioItem.user_id == user_id)
        .order_by(PortfolioItem.created_at.desc())
    )
    return list(result.scalars())


async def get_portfolio_item_by_id(
    db: AsyncSession, item_id: UUID, user_id: UUID
) -> PortfolioItem | None:
    result = await db.execute(
        select(PortfolioItem)
        .options(selectinload(PortfolioItem.lego_set))
        .where(PortfolioItem.id == item_id, PortfolioItem.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def update_portfolio_item(
    db: AsyncSession, item_id: UUID, user_id: UUID, item_data: dict[str, Any]
) -> PortfolioItem | None:
    item = await get_portfolio_item_by_id(db, item_id, user_id)
    if item is None:
        return None

    persisted_data = dict(item_data)
    if "set_number" in persisted_data:
        lego_set = await get_set_by_number(db, persisted_data.pop("set_number"))
        if lego_set is None:
            raise ValueError("LEGO set not found")
        item.lego_set_id = lego_set.id
        item.lego_set = lego_set

    for field_name, value in persisted_data.items():
        setattr(item, field_name, value)

    try:
        await db.flush()
    except SQLAlchemyError:
        logger.exception("unexpected DB failure while updating portfolio item")
        raise
    return await get_portfolio_item_by_id(db, item_id, user_id)


async def delete_portfolio_item(db: AsyncSession, item_id: UUID, user_id: UUID) -> bool:
    result = cast(
        CursorResult[Any],
        await db.execute(
            delete(PortfolioItem).where(
                PortfolioItem.id == item_id, PortfolioItem.user_id == user_id
            )
        ),
    )
    return bool(result.rowcount)


# Recommendation repository
async def create_recommendation(
    db: AsyncSession, recommendation_data: dict[str, Any]
) -> Recommendation:
    recommendation = Recommendation(**recommendation_data)
    db.add(recommendation)
    try:
        await db.flush()
        await db.refresh(recommendation)
    except SQLAlchemyError:
        logger.exception("unexpected DB failure while creating recommendation")
        raise
    return recommendation


async def get_latest_recommendation_for_set(
    db: AsyncSession, set_number: str
) -> Recommendation | None:
    normalized_set_number = normalize_set_number(set_number)
    result = await db.execute(
        select(Recommendation)
        .options(selectinload(Recommendation.lego_set))
        .join(LegoSet)
        .where(LegoSet.set_number == normalized_set_number)
        .order_by(Recommendation.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


# Watchlist repository
async def list_watchlist_items_for_user(
    db: AsyncSession, user_id: UUID, *, pagination: Pagination | None = None
) -> list[Any]:
    del db, user_id, pagination
    raise WatchlistRepositoryUnavailableError(
        "Watchlist persistence model is not defined."
    )
